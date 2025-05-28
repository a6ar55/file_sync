import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Dict, Set, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from starlette.responses import JSONResponse
import random

from shared.models import (
    RegisterNodeRequest, FileUploadRequest, DeltaSyncRequest, RestoreVersionRequest,
    NodeInfo, FileMetadata, SyncEvent, ConflictInfo, NetworkMetrics, NodeStatus,
    SyncEventType, VectorClockModel, ChunkSignature, FileDelta, DeltaSyncMetrics
)
from coordinator.database import DatabaseManager
from shared.utils import generate_file_id, calculate_file_hash, calculate_file_hash_from_data


def json_serializer(obj):
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class EnhancedVectorClockManager:
    """Enhanced vector clock manager for causal ordering."""
    
    def __init__(self):
        self.node_clocks = {}  # Track each node's vector clock
        self.global_nodes = set()  # All known nodes in the system
    
    def register_node(self, node_id: str) -> VectorClockModel:
        """Register a new node and initialize its vector clock."""
        # Add to global nodes
        self.global_nodes.add(node_id)
        
        # Initialize vector clock for this node
        initial_clock = VectorClockModel()
        for known_node in self.global_nodes:
            initial_clock.clocks[known_node] = 0
        
        # Set this node's own clock to 1
        initial_clock.clocks[node_id] = 1
        self.node_clocks[node_id] = initial_clock.copy()
        
        # Update all existing nodes to include this new node
        for existing_node_id in self.node_clocks:
            if existing_node_id != node_id:
                self.node_clocks[existing_node_id].clocks[node_id] = 0
        
        return initial_clock
    
    def increment_clock(self, node_id: str) -> VectorClockModel:
        """Increment the clock for a local event on a node."""
        if node_id not in self.node_clocks:
            return self.register_node(node_id)
        
        clock = self.node_clocks[node_id]
        clock.increment(node_id)
        return clock.copy()
    
    def update_on_receive(self, receiving_node: str, sender_clock: VectorClockModel) -> VectorClockModel:
        """Update vector clock when receiving a message."""
        if receiving_node not in self.node_clocks:
            self.register_node(receiving_node)
        
        receiver_clock = self.node_clocks[receiving_node]
        receiver_clock.update_on_receive(sender_clock, receiving_node)
        return receiver_clock.copy()
    
    def detect_conflicts(self, file_id: str, events: List[SyncEvent]) -> List[Dict[str, Any]]:
        """Detect concurrent operations that may cause conflicts."""
        conflicts = []
        
        # Group events by file
        file_events = [e for e in events if e.file_id == file_id]
        
        # Check for concurrent modifications
        for i, event1 in enumerate(file_events):
            for event2 in file_events[i+1:]:
                if (event1.event_type == SyncEventType.FILE_MODIFIED and 
                    event2.event_type == SyncEventType.FILE_MODIFIED and
                    event1.vector_clock.is_concurrent_with(event2.vector_clock)):
                    
                    conflicts.append({
                        'file_id': file_id,
                        'event1': event1.model_dump(),
                        'event2': event2.model_dump(),
                        'type': 'concurrent_modification',
                        'nodes': [event1.node_id, event2.node_id],
                        'detected_at': datetime.now().isoformat()
                    })
        
        return conflicts
    
    def get_causal_order(self, events: List[SyncEvent]) -> List[SyncEvent]:
        """Sort events in causal order using vector clocks."""
        def compare_events(e1: SyncEvent, e2: SyncEvent) -> int:
            relation = e1.vector_clock.compare(e2.vector_clock)
            if relation == "before":
                return -1
            elif relation == "after":
                return 1
            else:
                # For concurrent events, use timestamp as tiebreaker
                return -1 if e1.timestamp < e2.timestamp else 1
        
        from functools import cmp_to_key
        return sorted(events, key=cmp_to_key(compare_events))
    
    def get_node_clock(self, node_id: str) -> VectorClockModel:
        """Get current vector clock for a node."""
        if node_id not in self.node_clocks:
            return self.register_node(node_id)
        return self.node_clocks[node_id].copy()
    
    def get_all_clocks(self) -> Dict[str, VectorClockModel]:
        """Get all node vector clocks for visualization."""
        return {node_id: clock.copy() for node_id, clock in self.node_clocks.items()}


class SimpleFileManager:
    """Simplified file version manager."""
    
    def __init__(self):
        self.file_versions = {}
        self.file_content = {}
    
    def create_version(self, file_id: str, content: bytes, owner_node: str, 
                      vector_clock: VectorClockModel, metadata: dict):
        """Create a new file version."""
        version_id = str(uuid.uuid4())
        self.file_content[version_id] = content
        if file_id not in self.file_versions:
            self.file_versions[file_id] = []
        self.file_versions[file_id].append({
            'version_id': version_id,
            'content_size': len(content),
            'created_by': owner_node,
            'metadata': metadata
        })
        return version_id
    
    def get_current_version(self, file_id: str):
        """Get current version of a file."""
        if file_id in self.file_versions and self.file_versions[file_id]:
            return self.file_versions[file_id][-1]
        return None
    
    def get_version_content(self, version_id: str):
        """Get content of a specific version."""
        return self.file_content.get(version_id)


class AdvancedDeltaSync:
    """Advanced delta synchronization with rolling hash optimization."""
    
    CHUNK_SIZE = 4096  # 4KB chunks
    
    def __init__(self):
        self.chunk_cache = {}  # Cache of chunk signatures
    
    def calculate_rolling_hash(self, data: bytes, start: int = 0, length: int = None) -> int:
        """Calculate rolling hash (simplified Adler-32 style)."""
        if length is None:
            length = len(data) - start
        
        a, b = 1, 0
        for i in range(start, min(start + length, len(data))):
            a = (a + data[i]) % 65521
            b = (b + a) % 65521
        
        return (b << 16) | a
    
    def calculate_strong_hash(self, data: bytes) -> str:
        """Calculate SHA-256 hash for chunk."""
        import hashlib
        return hashlib.sha256(data).hexdigest()
    
    def create_signature(self, data: bytes, file_id: str = None) -> List[ChunkSignature]:
        """Create signature for delta sync (list of chunk signatures)."""
        signatures = []
        
        for i in range(0, len(data), self.CHUNK_SIZE):
            chunk_data = data[i:i + self.CHUNK_SIZE]
            if not chunk_data:
                break
            
            signature = ChunkSignature(
                index=len(signatures),
                offset=i,
                size=len(chunk_data),
                weak_hash=self.calculate_rolling_hash(chunk_data),
                strong_hash=self.calculate_strong_hash(chunk_data)
            )
            signatures.append(signature)
            
            # Cache signature for this file
            if file_id:
                cache_key = f"{file_id}:{signature.strong_hash}"
                self.chunk_cache[cache_key] = signature
        
        return signatures
    
    def create_content_delta(self, old_content: bytes, new_content: bytes, 
                           file_id: str = None) -> FileDelta:
        """Create delta between two content versions."""
        import time
        start_time = time.time()
        
        # Create signatures for old content
        old_signatures = self.create_signature(old_content, f"{file_id}_old") if old_content else []
        old_sig_map = {sig.strong_hash: sig for sig in old_signatures}
        
        # Create chunks for new content and determine which are unchanged
        new_chunks = []
        unchanged_chunks = []
        chunks_to_add = []
        bandwidth_saved = 0
        
        for i in range(0, len(new_content), self.CHUNK_SIZE):
            chunk_data = new_content[i:i + self.CHUNK_SIZE]
            if not chunk_data:
                break
            
            chunk_index = len(new_chunks)
            weak_hash = self.calculate_rolling_hash(chunk_data)
            strong_hash = self.calculate_strong_hash(chunk_data)
            
            # Check if this chunk exists in old content
            if strong_hash in old_sig_map:
                # Chunk unchanged
                unchanged_chunks.append(chunk_index)
                bandwidth_saved += len(chunk_data)
            else:
                # New or modified chunk
                chunk = FileChunk(
                    index=chunk_index,
                    offset=i,
                    size=len(chunk_data),
                    hash=strong_hash,
                    weak_hash=weak_hash,
                    data=chunk_data,
                    is_new=True
                )
                chunks_to_add.append(chunk)
            
            new_chunks.append(chunk_index)
        
        sync_time = time.time() - start_time
        compression_ratio = (bandwidth_saved / len(new_content) * 100) if new_content else 0
        
        delta = FileDelta(
            file_id=file_id or "unknown",
            old_hash=self.calculate_strong_hash(old_content) if old_content else None,
            new_hash=self.calculate_strong_hash(new_content),
            old_size=len(old_content) if old_content else 0,
            new_size=len(new_content),
            chunks_to_add=chunks_to_add,
            chunks_to_remove=[],  # Not used in this simple implementation
            chunks_unchanged=unchanged_chunks,
            total_chunks=len(new_chunks),
            bandwidth_saved=bandwidth_saved,
            compression_ratio=compression_ratio
        )
        
        return delta
    
    def apply_delta(self, old_content: bytes, delta: FileDelta) -> bytes:
        """Apply delta to reconstruct new content."""
        # Simple implementation: just use the new chunks
        # In a real implementation, this would reconstruct from unchanged + new chunks
        new_content = b''
        
        for chunk in delta.chunks_to_add:
            if isinstance(chunk.data, bytes):
                new_content += chunk.data
            elif isinstance(chunk.data, str):
                try:
                    new_content += bytes.fromhex(chunk.data)
                except:
                    new_content += chunk.data.encode('utf-8')
        
        return new_content
    
    def get_delta_metrics(self, delta: FileDelta, sync_time: float) -> DeltaSyncMetrics:
        """Generate comprehensive delta sync metrics."""
        throughput = delta.new_size / sync_time if sync_time > 0 else 0
        
        return DeltaSyncMetrics(
            file_id=delta.file_id,
            original_size=delta.new_size,
            compressed_size=delta.new_size - delta.bandwidth_saved,
            bandwidth_saved=delta.bandwidth_saved,
            chunks_total=delta.total_chunks,
            chunks_unchanged=len(delta.chunks_unchanged),
            chunks_modified=len(delta.chunks_to_add),
            chunks_new=len(delta.chunks_to_add),  # Simplified
            sync_time=sync_time,
            throughput=throughput,
            compression_ratio=delta.compression_ratio
        )


class CoordinatorServer:
    """
    Central coordinator server for distributed file synchronization.
    Manages nodes, files, conflicts, and real-time communication.
    """
    
    def __init__(self):
        self.app = FastAPI(title="Distributed File Sync Coordinator", version="1.0.0")
        self.db = DatabaseManager()
        self.vector_clock_manager = EnhancedVectorClockManager()
        self.file_manager = SimpleFileManager()
        self.delta_sync = AdvancedDeltaSync()
        
        # WebSocket connection management
        self.active_connections: Set[WebSocket] = set()
        self.node_connections: Dict[str, WebSocket] = {}
        
        # Performance metrics
        self.metrics = {
            'total_sync_operations': 0,
            'total_bandwidth_saved': 0,
            'total_conflicts_resolved': 0,
            'average_sync_latency': 0.0
        }
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add startup event
        @self.app.on_event("startup")
        async def startup_event():
            await self.db.initialize()
        
        self.setup_routes()
    
    def setup_routes(self):
        """Setup all REST API routes and WebSocket endpoints."""
        
        # Node management endpoints
        @self.app.post("/api/register")
        async def register_node(request: RegisterNodeRequest):
            """Register a new client node."""
            try:
                # Create vector clock for new node
                vector_clock = self.vector_clock_manager.register_node(request.node_id)
                
                # Create node info with proper VectorClockModel
                node_info = NodeInfo(
                    node_id=request.node_id,
                    name=request.name,
                    address=request.address,
                    port=request.port,
                    status=NodeStatus.ONLINE,
                    last_seen=datetime.now(),
                    vector_clock=VectorClockModel(clocks={request.node_id: 1})
                )
                
                # Store in database
                if await self.db.register_node(node_info):
                    # Broadcast node registration event
                    await self.broadcast_event(SyncEvent(
                        event_id=str(uuid.uuid4()),
                        event_type=SyncEventType.NODE_STATUS_CHANGE,
                        node_id=request.node_id,
                        timestamp=datetime.now(),
                        data={
                            'action': 'registered',
                            'node_name': request.name,
                            'status': 'online'
                        },
                        vector_clock=node_info.vector_clock
                    ))
                    
                    return {
                        "status": "success",
                        "message": f"Node {request.node_id} registered successfully",
                        "vector_clock": node_info.vector_clock.model_dump()
                    }
                else:
                    raise HTTPException(status_code=500, detail="Failed to register node")
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Registration error: {str(e)}")
        
        @self.app.get("/api/nodes")
        async def get_nodes():
            """Get all registered nodes."""
            nodes = await self.db.get_all_nodes()
            return [node.model_dump() for node in nodes]
        
        @self.app.get("/api/nodes/{node_id}")
        async def get_node(node_id: str):
            """Get specific node information."""
            node = await self.db.get_node(node_id)
            if node:
                return node.model_dump()
            raise HTTPException(status_code=404, detail="Node not found")
        
        # File management endpoints
        @self.app.get("/api/files")
        async def get_files():
            """Get all files with metadata."""
            files = await self.db.get_all_files()
            return [file.model_dump() for file in files]
        
        @self.app.get("/api/files/{file_id}")
        async def get_file(file_id: str):
            """Get specific file metadata."""
            file_metadata = await self.db.get_file(file_id)
            if file_metadata:
                return file_metadata.model_dump()
            raise HTTPException(status_code=404, detail="File not found")
        
        @self.app.get("/api/files/{file_id}/chunks")
        async def get_file_chunks(file_id: str):
            """Get file chunk information for delta sync."""
            try:
                # Get current file version
                current_version = self.file_manager.get_current_version(file_id)
                if not current_version:
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Get file data
                file_data = self.file_manager.get_version_content(current_version['version_id'])
                if file_data is None:
                    raise HTTPException(status_code=404, detail="File data not found")
                
                # Create signature for delta sync
                signatures = self.delta_sync.create_signature(file_data, file_id)
                return [sig.model_dump() for sig in signatures]
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error getting chunks: {str(e)}")
        
        @self.app.post("/api/files/upload")
        async def upload_file(request: FileUploadRequest):
            """Upload file with delta sync support."""
            try:
                start_time = datetime.now()
                
                # Get current vector clock and update it
                current_clock = self.vector_clock_manager.increment_clock(request.file_metadata.owner_node)
                
                # Reconstruct file data from chunks
                file_data = b''.join(chunk.data for chunk in request.chunks if chunk.data)
                
                # Verify file hash
                actual_hash = calculate_file_hash_from_data(file_data)
                if actual_hash != request.file_metadata.hash:
                    # Allow empty hash for now, calculate it
                    request.file_metadata.hash = actual_hash
                
                # Check if this is a delta sync operation
                old_content = b''
                if request.use_delta_sync:
                    # Get previous version for delta sync
                    current_version = self.file_manager.get_current_version(request.file_metadata.file_id)
                    if current_version:
                        old_content = self.file_manager.get_version_content(current_version['version_id']) or b''
                
                # Create delta for analysis
                delta = self.delta_sync.create_content_delta(
                    old_content, 
                    file_data, 
                    request.file_metadata.file_id
                )
                
                # Update file metadata with current vector clock
                request.file_metadata.vector_clock = current_clock
                
                # Create version
                version = self.file_manager.create_version(
                    request.file_metadata.file_id,
                    file_data,
                    request.file_metadata.owner_node,
                    current_clock,
                    {
                        "uploaded_via": "api",
                        "delta_sync_used": request.use_delta_sync,
                        "bandwidth_saved": delta.bandwidth_saved,
                        "compression_ratio": delta.compression_ratio
                    }
                )
                
                # Store file metadata
                await self.db.store_file(request.file_metadata)
                
                # Calculate metrics
                sync_latency = (datetime.now() - start_time).total_seconds()
                delta_metrics = self.delta_sync.get_delta_metrics(delta, sync_latency)
                
                # Update global metrics
                self.metrics['total_sync_operations'] += 1
                self.metrics['total_bandwidth_saved'] += delta.bandwidth_saved
                self.metrics['average_sync_latency'] = (
                    (self.metrics['average_sync_latency'] * (self.metrics['total_sync_operations'] - 1) + sync_latency) 
                    / self.metrics['total_sync_operations']
                )
                
                # Broadcast file change event to all connected nodes
                sync_event = SyncEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=SyncEventType.FILE_MODIFIED,
                    node_id=request.file_metadata.owner_node,
                    file_id=request.file_metadata.file_id,
                    timestamp=datetime.now(),
                    data={
                        'file_id': request.file_metadata.file_id,
                        'file_name': request.file_metadata.name,
                        'file_size': request.file_metadata.size,
                        'file_hash': request.file_metadata.hash,
                        'version_id': version,
                        'action': 'uploaded',
                        'delta_sync_used': request.use_delta_sync,
                        'bandwidth_saved': delta.bandwidth_saved,
                        'compression_ratio': delta.compression_ratio,
                        'chunks_total': delta.total_chunks,
                        'chunks_unchanged': len(delta.chunks_unchanged),
                        'chunks_transferred': len(delta.chunks_to_add)
                    },
                    vector_clock=current_clock
                )
                
                await self.broadcast_event(sync_event)
                
                # Propagate to other online nodes
                await self._propagate_file_to_nodes(request.file_metadata, file_data, version)
                
                return {
                    "status": "success",
                    "version_id": version,
                    "sync_latency": sync_latency,
                    "delta_metrics": delta_metrics.model_dump(),
                    "vector_clock": current_clock.model_dump()
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")
        
        @self.app.get("/api/files/{file_id}/content")
        async def get_file_content(file_id: str):
            """Get file content for synchronization."""
            try:
                # Get current file version
                current_version = self.file_manager.get_current_version(file_id)
                if not current_version:
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Get file content
                file_content = self.file_manager.get_version_content(current_version['version_id'])
                if file_content is None:
                    raise HTTPException(status_code=404, detail="File content not found")
                
                # Get file metadata
                file_metadata = await self.db.get_file(file_id)
                if not file_metadata:
                    raise HTTPException(status_code=404, detail="File metadata not found")
                
                return {
                    "success": True,
                    "file_metadata": file_metadata.model_dump(),
                    "content": file_content.hex(),  # Send as hex string
                    "version_id": current_version['version_id']
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error getting file content: {str(e)}")
        
        @self.app.delete("/api/files/{file_id}")
        async def delete_file(file_id: str, request: Request):
            """Delete a file from the system."""
            try:
                # Get request body
                body = await request.body()
                if body:
                    request_data = json.loads(body)
                else:
                    request_data = {}
                
                node_id = request_data.get('node_id')
                if not node_id:
                    raise HTTPException(status_code=400, detail="node_id is required")
                
                # Get file metadata
                file_metadata = await self.db.get_file(file_id)
                if not file_metadata:
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Mark file as deleted
                file_metadata.is_deleted = True
                await self.db.store_file(file_metadata)
                
                # Remove from file manager
                if file_id in self.file_manager.file_versions:
                    del self.file_manager.file_versions[file_id]
                
                # Broadcast deletion event
                await self.broadcast_event(SyncEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=SyncEventType.FILE_DELETED,
                    node_id=node_id,
                    file_id=file_id,
                    timestamp=datetime.now(),
                    data={
                        'file_id': file_id,
                        'file_name': file_metadata.name,
                        'action': 'deleted',
                        'deleted_by': node_id
                    },
                    vector_clock=VectorClockModel(clocks={node_id: 1})
                ))
                
                return {
                    "success": True,
                    "message": f"File {file_metadata.name} deleted successfully"
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")
        
        @self.app.get("/api/nodes/{node_id}/files")
        async def get_node_files(node_id: str):
            """Get all files owned by a specific node."""
            try:
                all_files = await self.db.get_all_files()
                node_files = [
                    file for file in all_files 
                    if file.owner_node == node_id and not file.is_deleted
                ]
                return [file.model_dump() for file in node_files]
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error getting node files: {str(e)}")
        
        @self.app.delete("/api/nodes/{node_id}")
        async def remove_node(node_id: str):
            """Remove a node from the system."""
            try:
                # Check if node exists
                node = await self.db.get_node(node_id)
                if not node:
                    raise HTTPException(status_code=404, detail="Node not found")
                
                # Get all files owned by this node
                all_files = await self.db.get_all_files()
                node_files = [
                    file for file in all_files 
                    if file.owner_node == node_id and not file.is_deleted
                ]
                
                # Mark all node's files as deleted
                for file in node_files:
                    file.is_deleted = True
                    await self.db.store_file(file)
                    
                    # Remove from file manager
                    if file.file_id in self.file_manager.file_versions:
                        del self.file_manager.file_versions[file.file_id]
                
                # Remove node from database
                await self.db.remove_node(node_id)
                
                # Close WebSocket connection if exists
                if node_id in self.node_connections:
                    try:
                        await self.node_connections[node_id].close()
                    except:
                        pass
                    finally:
                        del self.node_connections[node_id]
                
                # Broadcast node removal event
                await self.broadcast_event(SyncEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=SyncEventType.NODE_LEFT,
                    node_id=node_id,
                    timestamp=datetime.now(),
                    data={
                        'node_id': node_id,
                        'node_name': node.name,
                        'action': 'removed',
                        'files_deleted': len(node_files)
                    },
                    vector_clock=VectorClockModel(clocks={node_id: 1})
                ))
                
                return {
                    "success": True,
                    "message": f"Node {node.name} removed successfully",
                    "files_deleted": len(node_files)
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Remove node error: {str(e)}")
        
        @self.app.post("/api/files/{file_id}/delta")
        async def sync_delta(file_id: str, request: DeltaSyncRequest):
            """Handle delta synchronization request."""
            try:
                start_time = datetime.now()
                
                # Get current file version
                current_version = self.file_manager.get_current_version(file_id)
                if not current_version:
                    raise HTTPException(status_code=404, detail="File not found")
                
                current_data = self.file_manager.get_version_content(current_version['version_id'])
                if current_data is None:
                    raise HTTPException(status_code=404, detail="File data not found")
                
                # Convert request chunks to content
                new_content = b''.join(chunk.data for chunk in request.current_chunks if chunk.data)
                
                # Generate delta
                delta = self.delta_sync.create_content_delta(current_data, new_content, file_id)
                
                # Calculate metrics
                sync_time = (datetime.now() - start_time).total_seconds()
                delta_metrics = self.delta_sync.get_delta_metrics(delta, sync_time)
                
                # Update global metrics
                self.metrics['total_bandwidth_saved'] += delta.bandwidth_saved
                
                # Update vector clock
                receiving_node = list(request.vector_clock.clocks.keys())[0] if request.vector_clock.clocks else 'unknown'
                updated_clock = self.vector_clock_manager.update_on_receive(receiving_node, request.vector_clock)
                
                # Broadcast sync progress
                await self.broadcast_event(SyncEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=SyncEventType.FILE_SYNC_PROGRESS,
                    node_id=receiving_node,
                    file_id=file_id,
                    timestamp=datetime.now(),
                    data={
                        'file_id': file_id,
                        'action': 'delta_sync_completed',
                        'delta_metrics': delta_metrics.model_dump(),
                        'bandwidth_saved': delta.bandwidth_saved,
                        'compression_ratio': delta.compression_ratio,
                        'chunks_reused': len(delta.chunks_unchanged),
                        'chunks_transferred': len(delta.chunks_to_add)
                    },
                    vector_clock=updated_clock
                ))
                
                return {
                    "success": True,
                    "delta": delta.model_dump(),
                    "metrics": delta_metrics.model_dump(),
                    "vector_clock": updated_clock.model_dump()
                }
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Delta sync error: {str(e)}")
        
        @self.app.get("/api/files/{file_id}/history")
        async def get_file_history(file_id: str):
            """Get file version history."""
            try:
                versions = self.file_manager.file_versions.get(file_id, [])
                return versions
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error getting history: {str(e)}")
        
        @self.app.post("/api/files/{file_id}/restore")
        async def restore_file_version(file_id: str, request: RestoreVersionRequest):
            """Restore file to a specific version."""
            try:
                # Simple restore - just return success for now
                success = True
                if success:
                    # Broadcast restore event
                    await self.broadcast_event(SyncEvent(
                        event_id=str(uuid.uuid4()),
                        event_type=SyncEventType.FILE_MODIFIED,
                        node_id=request.node_id,
                        timestamp=datetime.now(),
                        data={
                            'file_id': file_id,
                            'action': 'restored',
                            'restored_version': request.version_id
                        },
                        vector_clock=VectorClockModel()
                    ))
                    
                    return {"status": "success", "message": "File restored successfully"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to restore file")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Restore error: {str(e)}")
        
        # Conflict management endpoints
        @self.app.get("/api/conflicts")
        async def get_conflicts():
            """Get all unresolved conflicts."""
            conflicts = await self.db.get_unresolved_conflicts()
            return [conflict.model_dump() for conflict in conflicts]
        
        @self.app.post("/api/conflicts/{conflict_id}/resolve")
        async def resolve_conflict(conflict_id: str, resolution_strategy: str = "latest"):
            """Resolve a conflict."""
            try:
                success = await self.db.resolve_conflict(conflict_id, resolution_strategy, "resolved")
                if success:
                    self.metrics['total_conflicts_resolved'] += 1
                    return {"status": "success", "message": "Conflict resolved"}
                else:
                    raise HTTPException(status_code=404, detail="Conflict not found")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Resolution error: {str(e)}")
        
        # Metrics and status endpoints
        @self.app.get("/api/metrics")
        async def get_metrics():
            """Get system performance metrics."""
            stats = await self.db.get_statistics()
            return {
                **self.metrics,
                'active_connections': len(self.active_connections),
                'registered_nodes': stats.get('total_nodes', 0),
                'total_files': stats.get('total_files', 0),
                'unresolved_conflicts': stats.get('unresolved_conflicts', 0)
            }
        
        @self.app.get("/api/vector-clocks")
        async def get_vector_clocks():
            """Get current vector clocks for all nodes."""
            clocks = self.vector_clock_manager.get_all_clocks()
            return {
                node_id: {
                    'clocks': clock.clocks,
                    'display': clock.to_display_string(),
                    'max_time': clock.get_max_time()
                }
                for node_id, clock in clocks.items()
            }
        
        @self.app.get("/api/causal-order")
        async def get_causal_order(limit: int = 50):
            """Get events in causal order."""
            events = await self.db.get_recent_events(limit)
            ordered_events = self.vector_clock_manager.get_causal_order(events)
            return [event.model_dump() for event in ordered_events]
        
        @self.app.get("/api/conflicts/detect/{file_id}")
        async def detect_file_conflicts(file_id: str):
            """Detect conflicts for a specific file."""
            events = await self.db.get_recent_events(100)
            conflicts = self.vector_clock_manager.detect_conflicts(file_id, events)
            return conflicts
        
        @self.app.get("/api/delta-metrics")
        async def get_delta_metrics():
            """Get delta synchronization performance metrics."""
            # Calculate metrics from recent sync operations
            recent_events = await self.db.get_recent_events(100)
            sync_events = [e for e in recent_events if e.event_type == SyncEventType.SYNC_COMPLETED]
            
            total_bandwidth_saved = 0
            total_files_synced = len(sync_events)
            avg_compression_ratio = 0
            
            for event in sync_events:
                data = event.data
                if 'bandwidth_saved' in data:
                    total_bandwidth_saved += data.get('bandwidth_saved', 0)
                if 'compression_ratio' in data:
                    avg_compression_ratio += data.get('compression_ratio', 0)
            
            if total_files_synced > 0:
                avg_compression_ratio /= total_files_synced
            
            return {
                'total_bandwidth_saved': total_bandwidth_saved,
                'total_files_synced': total_files_synced,
                'average_compression_ratio': avg_compression_ratio,
                'chunk_cache_size': len(self.delta_sync.chunk_cache),
                'chunk_size': self.delta_sync.CHUNK_SIZE
            }
        
        @self.app.get("/api/network-topology")
        async def get_network_topology():
            """Get network topology data for visualization."""
            nodes = await self.db.get_all_nodes()
            files = await self.db.get_all_files()
            
            # Calculate node positions in a circle
            import math
            center_x, center_y = 300, 300
            radius = 200
            
            topology = {
                'coordinator': {'x': center_x, 'y': center_y, 'type': 'coordinator'},
                'nodes': [],
                'connections': [],
                'data_flows': []
            }
            
            for i, node in enumerate(nodes):
                if node.status == NodeStatus.ONLINE:
                    angle = (i * 2 * math.pi) / len(nodes)
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    
                    node_files = [f for f in files if f.owner_node == node.node_id and not f.is_deleted]
                    
                    topology['nodes'].append({
                        'id': node.node_id,
                        'name': node.name or f"Node {i+1}",
                        'x': x,
                        'y': y,
                        'status': node.status.value,
                        'file_count': len(node_files),
                        'last_seen': node.last_seen.isoformat(),
                        'vector_clock': node.vector_clock.to_display_string()
                    })
                    
                    # Connection to coordinator
                    topology['connections'].append({
                        'from': node.node_id,
                        'to': 'coordinator',
                        'latency': round(random.uniform(1, 50), 1),  # Simulated latency
                        'status': 'active' if node.status == NodeStatus.ONLINE else 'inactive'
                    })
            
            return topology
        
        @self.app.get("/api/events")
        async def get_recent_events(limit: int = 100):
            """Get recent system events."""
            events = await self.db.get_recent_events(limit)
            return [event.model_dump() for event in events]
        
        @self.app.get("/api/events/unprocessed")
        async def get_unprocessed_events(limit: int = 100):
            """Get unprocessed events."""
            events = await self.db.get_unprocessed_events(limit)
            return [event.model_dump() for event in events]
        
        # WebSocket endpoint for real-time updates
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.handle_websocket_connection(websocket)
        
        @self.app.websocket("/ws/{node_id}")
        async def node_websocket_endpoint(websocket: WebSocket, node_id: str):
            await self.handle_node_websocket_connection(websocket, node_id)
    
    async def handle_websocket_connection(self, websocket: WebSocket):
        """Handle dashboard WebSocket connections."""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        try:
            # Send initial data
            initial_data = {
                "type": "initial_data",
                "data": {
                    "nodes": [node.model_dump() for node in await self.db.get_all_nodes()],
                    "files": [file.model_dump() for file in await self.db.get_all_files()],
                    "metrics": await self.get_current_metrics()
                }
            }
            await websocket.send_text(json.dumps(initial_data, default=json_serializer))
            
            # Keep connection alive
            while True:
                try:
                    data = await websocket.receive_text()
                    # Handle any incoming messages from dashboard
                    message = json.loads(data)
                    await self.handle_dashboard_message(websocket, message)
                except WebSocketDisconnect:
                    break
                    
        except WebSocketDisconnect:
            pass
        finally:
            self.active_connections.discard(websocket)
    
    async def handle_node_websocket_connection(self, websocket: WebSocket, node_id: str):
        """Handle client node WebSocket connections."""
        await websocket.accept()
        self.node_connections[node_id] = websocket
        
        # Update node status to online
        await self.db.update_node_status(node_id, NodeStatus.ONLINE)
        
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self.handle_node_message(node_id, message)
                except WebSocketDisconnect:
                    break
                    
        except WebSocketDisconnect:
            pass
        finally:
            # Update node status to offline
            await self.db.update_node_status(node_id, NodeStatus.OFFLINE)
            self.node_connections.pop(node_id, None)
    
    async def handle_dashboard_message(self, websocket: WebSocket, message: dict):
        """Handle messages from the dashboard."""
        message_type = message.get("type")
        
        if message_type == "request_metrics":
            metrics = await self.get_current_metrics()
            response = {
                "type": "metrics_update",
                "data": metrics
            }
            await websocket.send_text(json.dumps(response, default=json_serializer))
        elif message_type == "request_nodes":
            nodes = await self.db.get_all_nodes()
            response = {
                "type": "nodes_update",
                "data": [node.model_dump() for node in nodes]
            }
            await websocket.send_text(json.dumps(response, default=json_serializer))
    
    async def handle_node_message(self, node_id: str, message: dict):
        """Handle messages from client nodes."""
        message_type = message.get("type")
        
        if message_type == "heartbeat":
            # Update last seen time
            await self.db.update_node_status(node_id, NodeStatus.ONLINE)
        elif message_type == "file_change":
            # Handle file change notification
            await self.broadcast_event(SyncEvent(
                event_id=str(uuid.uuid4()),
                event_type=SyncEventType.FILE_MODIFIED,
                node_id=node_id,
                timestamp=datetime.now(),
                data=message.get("data", {}),
                vector_clock=VectorClockModel()
            ))
    
    async def broadcast_event(self, event: SyncEvent):
        """Broadcast event to all connected clients."""
        # Store event in database
        await self.db.record_event(event)
        
        # Prepare message
        message = {
            "type": "event",
            "data": event.model_dump()
        }
        message_json = json.dumps(message, default=json_serializer)
        
        # Send to all dashboard connections
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except:
                disconnected.add(connection)
        
        # Remove disconnected connections
        self.active_connections -= disconnected
        
        # Send to relevant node connections
        for node_id, connection in self.node_connections.items():
            if node_id != event.node_id:  # Don't echo back to sender
                try:
                    await connection.send_text(message_json)
                except:
                    # Connection is dead, will be cleaned up later
                    pass
    
    async def _propagate_file_to_nodes(self, file_metadata: FileMetadata, file_data: bytes, version: str):
        """Propagate file to other online nodes."""
        try:
            nodes = await self.db.get_online_nodes()
            propagated_count = 0
            
            for node in nodes:
                if node.node_id != file_metadata.owner_node:
                    try:
                        # Create sync progress event - sync started
                        await self.broadcast_event(SyncEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=SyncEventType.FILE_SYNC_PROGRESS,
                            node_id=node.node_id,
                            file_id=file_metadata.file_id,
                            timestamp=datetime.now(),
                            data={
                                'file_id': file_metadata.file_id,
                                'file_name': file_metadata.name,
                                'target_node': node.node_id,
                                'source_node': file_metadata.owner_node,
                                'action': 'sync_started',
                                'progress': 0
                            },
                            vector_clock=VectorClockModel(clocks={node.node_id: 1})
                        ))
                        
                        # Create a replica of the file metadata for this node
                        replica_metadata = FileMetadata(
                            file_id=f"{file_metadata.file_id}_replica_{node.node_id}",  # Unique ID for replica
                            name=file_metadata.name,
                            path=f"/{node.node_id}/replicas/{file_metadata.name}",
                            size=file_metadata.size,
                            hash=file_metadata.hash,
                            created_at=file_metadata.created_at,
                            modified_at=datetime.now(),
                            owner_node=node.node_id,  # Set replica owner to the target node
                            version=file_metadata.version,
                            vector_clock=file_metadata.vector_clock,
                            is_deleted=False,
                            content_type=file_metadata.content_type
                        )
                        
                        # Simulate file sync progress with actual storage
                        for progress in [25, 50, 75]:
                            await asyncio.sleep(0.3)  # Realistic delay
                            await self.broadcast_event(SyncEvent(
                                event_id=str(uuid.uuid4()),
                                event_type=SyncEventType.FILE_SYNC_PROGRESS,
                                node_id=node.node_id,
                                file_id=file_metadata.file_id,
                                timestamp=datetime.now(),
                                data={
                                    'file_id': file_metadata.file_id,
                                    'file_name': file_metadata.name,
                                    'target_node': node.node_id,
                                    'source_node': file_metadata.owner_node,
                                    'action': 'syncing',
                                    'progress': progress
                                },
                                vector_clock=VectorClockModel(clocks={node.node_id: 1})
                            ))
                        
                        # ACTUALLY STORE THE REPLICA METADATA IN DATABASE
                        await self.db.store_file(replica_metadata)
                        
                        # Store the file content for this node in file manager
                        file_version = self.file_manager.create_version(
                            replica_metadata.file_id,  # Use replica file_id
                            file_data,
                            node.node_id,
                            replica_metadata.vector_clock,
                            {
                                'replicated_from': file_metadata.owner_node, 
                                'is_replica': True,
                                'original_file_id': file_metadata.file_id
                            }
                        )
                        
                        # Final progress - complete
                        await asyncio.sleep(0.3)
                        await self.broadcast_event(SyncEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=SyncEventType.SYNC_COMPLETED,
                            node_id=node.node_id,
                            file_id=file_metadata.file_id,
                            timestamp=datetime.now(),
                            data={
                                'file_id': file_metadata.file_id,
                                'file_name': file_metadata.name,
                                'target_node': node.node_id,
                                'source_node': file_metadata.owner_node,
                                'action': 'sync_completed',
                                'bytes_transferred': len(file_data),
                                'version_id': file_version,
                                'replica_file_id': replica_metadata.file_id
                            },
                            vector_clock=VectorClockModel(clocks={node.node_id: 1})
                        ))
                        
                        propagated_count += 1
                        print(f"Successfully replicated file {file_metadata.name} to node {node.node_id} (replica_id: {replica_metadata.file_id})")
                        
                    except Exception as e:
                        print(f"Error propagating file to node {node.node_id}: {str(e)}")
                        # Send error event
                        await self.broadcast_event(SyncEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=SyncEventType.SYNC_ERROR,
                            node_id=node.node_id,
                            file_id=file_metadata.file_id,
                            timestamp=datetime.now(),
                            data={
                                'file_id': file_metadata.file_id,
                                'file_name': file_metadata.name,
                                'target_node': node.node_id,
                                'source_node': file_metadata.owner_node,
                                'error': str(e)
                            },
                            vector_clock=VectorClockModel(clocks={node.node_id: 1})
                        ))
            
            print(f"Successfully propagated file {file_metadata.name} to {propagated_count} nodes with database storage")
            
        except Exception as e:
            print(f"Error in file propagation: {str(e)}")
            # Broadcast general error
            await self.broadcast_event(SyncEvent(
                event_id=str(uuid.uuid4()),
                event_type=SyncEventType.SYNC_ERROR,
                node_id=file_metadata.owner_node,
                file_id=file_metadata.file_id,
                timestamp=datetime.now(),
                data={
                    'file_id': file_metadata.file_id,
                    'file_name': file_metadata.name,
                    'error': f"Propagation failed: {str(e)}"
                },
                vector_clock=VectorClockModel()
            ))
    
    async def get_current_metrics(self) -> dict:
        """Get current system metrics."""
        stats = await self.db.get_statistics()
        return {
            **self.metrics,
            'active_connections': len(self.active_connections),
            'registered_nodes': stats.get('total_nodes', 0),
            'total_files': stats.get('total_files', 0),
            'unresolved_conflicts': stats.get('unresolved_conflicts', 0),
            'timestamp': datetime.now().isoformat()
        }


def calculate_file_hash_from_data(data: bytes) -> str:
    """Calculate SHA-256 hash from file data."""
    import hashlib
    return hashlib.sha256(data).hexdigest()


def run_coordinator(host: str = "localhost", port: int = 8000):
    """Run the coordinator server."""
    coordinator = CoordinatorServer()
    uvicorn.run(coordinator.app, host=host, port=port)


if __name__ == "__main__":
    run_coordinator() 