import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Callable
import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from shared.models import (
    FileMetadata, FileChunk, RegisterNodeRequest, FileUploadRequest,
    DeltaSyncRequest, VectorClockModel, SyncEvent, SyncEventType
)
from shared.utils import (
    generate_file_id, calculate_file_hash, safe_file_read, safe_file_write,
    get_file_info, ensure_directory
)
from coordinator.vector_clock import VectorClock
from coordinator.delta_sync import DeltaSync


class SyncEngine:
    """
    Client-side synchronization engine that handles communication with the coordinator
    and manages local file synchronization.
    """
    
    def __init__(self, 
                 node_id: str,
                 node_name: str,
                 coordinator_url: str = "http://localhost:8000",
                 local_storage_path: str = "client_storage"):
        self.node_id = node_id
        self.node_name = node_name
        self.coordinator_url = coordinator_url
        self.local_storage_path = local_storage_path
        
        # Initialize components
        self.vector_clock: Optional[VectorClock] = None
        self.delta_sync = DeltaSync()
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # WebSocket connection for real-time updates
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.websocket_url = coordinator_url.replace("http", "ws") + f"/ws/{node_id}"
        
        # Local file tracking
        self.local_files: Dict[str, FileMetadata] = {}
        self.sync_queue: List[Dict] = []
        self.is_syncing = False
        
        # Event callbacks
        self.on_file_synced: Optional[Callable[[str, str], None]] = None
        self.on_conflict_detected: Optional[Callable[[str, dict], None]] = None
        self.on_sync_progress: Optional[Callable[[str, float], None]] = None
        
        # Ensure storage directory exists
        ensure_directory(local_storage_path)
        
        # Performance metrics
        self.metrics = {
            'files_synced': 0,
            'bytes_transferred': 0,
            'bytes_saved': 0,
            'sync_operations': 0,
            'conflicts_detected': 0
        }
    
    async def initialize(self) -> bool:
        """Initialize the sync engine and register with coordinator."""
        try:
            # Register with coordinator
            registration_data = RegisterNodeRequest(
                node_id=self.node_id,
                name=self.node_name,
                address="localhost",  # Client address
                port=0  # Client doesn't need to serve HTTP
            )
            
            response = await self.http_client.post(
                f"{self.coordinator_url}/api/register",
                json=registration_data.model_dump()
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Initialize vector clock from coordinator response
                vc_data = result.get('vector_clock', {})
                self.vector_clock = VectorClock.from_dict(vc_data)
                
                print(f"Successfully registered with coordinator: {result['message']}")
                
                # Start WebSocket connection
                await self._start_websocket_connection()
                
                return True
            else:
                print(f"Failed to register with coordinator: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error initializing sync engine: {e}")
            return False
    
    async def _start_websocket_connection(self):
        """Start WebSocket connection for real-time updates."""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            print(f"WebSocket connected to {self.websocket_url}")
            
            # Start listening for messages
            asyncio.create_task(self._websocket_listener())
            
            # Start heartbeat
            asyncio.create_task(self._heartbeat_loop())
            
        except Exception as e:
            print(f"Failed to connect WebSocket: {e}")
    
    async def _websocket_listener(self):
        """Listen for WebSocket messages from coordinator."""
        try:
            while self.websocket:
                try:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    await self._handle_websocket_message(data)
                except ConnectionClosed:
                    print("WebSocket connection closed")
                    break
                except Exception as e:
                    print(f"Error handling WebSocket message: {e}")
        except Exception as e:
            print(f"WebSocket listener error: {e}")
    
    async def _handle_websocket_message(self, data: dict):
        """Handle incoming WebSocket messages."""
        message_type = data.get("type")
        
        if message_type == "event":
            event_data = data.get("data", {})
            event_type = event_data.get("event_type")
            
            if event_type == SyncEventType.FILE_MODIFIED.value:
                # Another node modified a file
                await self._handle_remote_file_change(event_data)
            elif event_type == SyncEventType.CONFLICT_DETECTED.value:
                # Conflict detected by coordinator
                await self._handle_conflict_notification(event_data)
            elif event_type == SyncEventType.VECTOR_CLOCK_UPDATE.value:
                # Update vector clock
                await self._handle_vector_clock_update(event_data)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat messages to coordinator."""
        while self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }))
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
            except Exception as e:
                print(f"Heartbeat error: {e}")
                break
    
    async def sync_file(self, file_path: str, event_type: str = "modified") -> bool:
        """Sync a single file with the coordinator."""
        try:
            if not os.path.exists(file_path):
                if event_type == "deleted":
                    return await self._handle_file_deletion(file_path)
                else:
                    print(f"File does not exist: {file_path}")
                    return False
            
            # Get file information
            file_info = get_file_info(file_path)
            if not file_info['exists']:
                return False
            
            # Calculate file hash
            file_hash = calculate_file_hash(file_path)
            
            # Generate file ID (use path-based ID for consistency)
            file_id = generate_file_id(file_path)
            
            # Create file metadata
            if self.vector_clock:
                self.vector_clock.increment()
            
            file_metadata = FileMetadata(
                file_id=file_id,
                path=file_path,
                name=os.path.basename(file_path),
                size=file_info['size'],
                hash=file_hash,
                modified_time=file_info['modified_time'],
                version=str(datetime.now().timestamp()),
                vector_clock=VectorClockModel(
                    node_id=self.vector_clock.node_id if self.vector_clock else self.node_id,
                    clock=self.vector_clock.clock if self.vector_clock else [0] * 4,
                    node_mapping=self.vector_clock.node_mapping if self.vector_clock else {}
                ),
                node_id=self.node_id
            )
            
            # Check if we should use delta sync
            if await self._should_use_delta_sync(file_id, file_hash):
                return await self._sync_with_delta(file_path, file_metadata)
            else:
                return await self._sync_full_file(file_path, file_metadata)
                
        except Exception as e:
            print(f"Error syncing file {file_path}: {e}")
            return False
    
    async def _should_use_delta_sync(self, file_id: str, current_hash: str) -> bool:
        """Determine if delta sync should be used."""
        try:
            # Get current file metadata from coordinator
            response = await self.http_client.get(f"{self.coordinator_url}/api/files/{file_id}")
            
            if response.status_code == 200:
                remote_metadata = response.json()
                return remote_metadata.get('hash') != current_hash
            
            return False  # File doesn't exist on coordinator, use full sync
            
        except Exception:
            return False  # Default to full sync on error
    
    async def _sync_with_delta(self, file_path: str, file_metadata: FileMetadata) -> bool:
        """Sync file using delta synchronization."""
        try:
            # Calculate current file chunks
            chunks = self.delta_sync.calculate_file_chunks(file_path)
            
            # Request delta from coordinator
            delta_request = DeltaSyncRequest(
                file_id=file_metadata.file_id,
                current_version=file_metadata.version,
                current_chunks=chunks,
                vector_clock=file_metadata.vector_clock
            )
            
            response = await self.http_client.post(
                f"{self.coordinator_url}/api/files/{file_metadata.file_id}/delta",
                json=delta_request.model_dump()
            )
            
            if response.status_code == 200:
                result = response.json()
                delta_data = result.get('delta', {})
                bandwidth_savings = result.get('bandwidth_savings', 0)
                
                print(f"Delta sync completed for {file_path}")
                print(f"Bandwidth savings: {bandwidth_savings:.1f}%")
                
                # Update metrics
                self.metrics['sync_operations'] += 1
                self.metrics['bytes_saved'] += int(file_metadata.size * bandwidth_savings / 100)
                
                # Update local file tracking
                self.local_files[file_metadata.file_id] = file_metadata
                
                if self.on_sync_progress:
                    self.on_sync_progress(file_path, 100.0)
                
                return True
            else:
                print(f"Delta sync failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error in delta sync for {file_path}: {e}")
            return False
    
    async def _sync_full_file(self, file_path: str, file_metadata: FileMetadata) -> bool:
        """Sync entire file with coordinator."""
        try:
            # Read file data
            file_data = safe_file_read(file_path)
            if not file_data:
                print(f"Failed to read file: {file_path}")
                return False
            
            # Create file chunks
            chunks = self.delta_sync.calculate_file_chunks(file_path)
            
            # Create upload request
            upload_request = FileUploadRequest(
                file_metadata=file_metadata,
                chunks=chunks,
                vector_clock=file_metadata.vector_clock
            )
            
            # Upload to coordinator
            response = await self.http_client.post(
                f"{self.coordinator_url}/api/files/upload",
                json=upload_request.model_dump()
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Full sync completed for {file_path}")
                print(f"Version ID: {result.get('version_id')}")
                
                # Update metrics
                self.metrics['files_synced'] += 1
                self.metrics['bytes_transferred'] += file_metadata.size
                self.metrics['sync_operations'] += 1
                
                # Update local file tracking
                self.local_files[file_metadata.file_id] = file_metadata
                
                if self.on_file_synced:
                    self.on_file_synced(file_path, result.get('version_id', ''))
                
                if self.on_sync_progress:
                    self.on_sync_progress(file_path, 100.0)
                
                return True
            else:
                print(f"Full sync failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error in full sync for {file_path}: {e}")
            return False
    
    async def _handle_file_deletion(self, file_path: str) -> bool:
        """Handle file deletion synchronization."""
        try:
            # Find file in local tracking
            file_id = None
            for fid, metadata in self.local_files.items():
                if metadata.path == file_path:
                    file_id = fid
                    break
            
            if not file_id:
                print(f"File not found in local tracking: {file_path}")
                return False
            
            # For now, just remove from local tracking
            # In a full implementation, you would notify the coordinator
            del self.local_files[file_id]
            print(f"Removed deleted file from tracking: {file_path}")
            
            return True
            
        except Exception as e:
            print(f"Error handling file deletion {file_path}: {e}")
            return False
    
    async def _handle_remote_file_change(self, event_data: dict):
        """Handle file changes from other nodes."""
        try:
            file_id = event_data.get('data', {}).get('file_id')
            if not file_id:
                return
            
            # Get updated file metadata from coordinator
            response = await self.http_client.get(f"{self.coordinator_url}/api/files/{file_id}")
            
            if response.status_code == 200:
                remote_metadata = FileMetadata(**response.json())
                
                # Check if we need to update local file
                local_metadata = self.local_files.get(file_id)
                
                if not local_metadata or local_metadata.hash != remote_metadata.hash:
                    print(f"Remote file change detected: {remote_metadata.name}")
                    # In a full implementation, you would download and apply changes
                    await self._download_file_from_coordinator(file_id, remote_metadata)
                    
        except Exception as e:
            print(f"Error handling remote file change: {e}")
    
    async def _download_file_from_coordinator(self, file_id: str, metadata: FileMetadata):
        """Download file from coordinator (simplified implementation)."""
        try:
            # In a full implementation, this would:
            # 1. Get file chunks from coordinator
            # 2. Apply delta if possible
            # 3. Reconstruct file locally
            # 4. Update local tracking
            
            print(f"Would download file: {metadata.name} (ID: {file_id})")
            self.local_files[file_id] = metadata
            
        except Exception as e:
            print(f"Error downloading file {file_id}: {e}")
    
    async def _handle_conflict_notification(self, event_data: dict):
        """Handle conflict notifications from coordinator."""
        try:
            conflict_info = event_data.get('data', {})
            file_id = conflict_info.get('file_id')
            
            print(f"Conflict detected for file: {file_id}")
            self.metrics['conflicts_detected'] += 1
            
            if self.on_conflict_detected:
                self.on_conflict_detected(file_id, conflict_info)
                
        except Exception as e:
            print(f"Error handling conflict notification: {e}")
    
    async def _handle_vector_clock_update(self, event_data: dict):
        """Handle vector clock updates from coordinator."""
        try:
            vc_data = event_data.get('data', {}).get('vector_clock')
            if vc_data and self.vector_clock:
                self.vector_clock.update(vc_data.get('clock', []), event_data.get('node_id', ''))
                
        except Exception as e:
            print(f"Error handling vector clock update: {e}")
    
    async def get_file_history(self, file_id: str) -> List[dict]:
        """Get version history for a file."""
        try:
            response = await self.http_client.get(f"{self.coordinator_url}/api/files/{file_id}/history")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get file history: {response.text}")
                return []
                
        except Exception as e:
            print(f"Error getting file history: {e}")
            return []
    
    async def restore_file_version(self, file_id: str, version_id: str) -> bool:
        """Restore a file to a specific version."""
        try:
            from shared.models import RestoreVersionRequest
            
            restore_request = RestoreVersionRequest(
                file_id=file_id,
                version_id=version_id,
                node_id=self.node_id
            )
            
            response = await self.http_client.post(
                f"{self.coordinator_url}/api/files/{file_id}/restore",
                json=restore_request.model_dump()
            )
            
            if response.status_code == 200:
                print(f"Successfully restored file to version {version_id}")
                return True
            else:
                print(f"Failed to restore file: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error restoring file version: {e}")
            return False
    
    def get_sync_stats(self) -> dict:
        """Get synchronization statistics."""
        return {
            **self.metrics,
            'local_files': len(self.local_files),
            'is_connected': self.websocket is not None,
            'node_id': self.node_id,
            'vector_clock': self.vector_clock.to_dict() if self.vector_clock else None
        }
    
    async def shutdown(self):
        """Cleanup and shutdown the sync engine."""
        try:
            if self.websocket:
                await self.websocket.close()
            
            await self.http_client.aclose()
            print("Sync engine shutdown complete")
            
        except Exception as e:
            print(f"Error during shutdown: {e}") 