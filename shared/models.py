"""
Shared data models for the distributed file synchronization system.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
import hashlib
import json


class NodeStatus(str, Enum):
    """Status of a node in the network."""
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    ERROR = "error"


class SyncEventType(str, Enum):
    """Types of synchronization events."""
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    FILE_MOVED = "file_moved"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    NODE_JOINED = "node_joined"
    NODE_LEFT = "node_left"
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    NODE_STATUS_CHANGE = "node_status_change"
    VECTOR_CLOCK_UPDATE = "vector_clock_update"
    FILE_SYNC_PROGRESS = "file_sync_progress"


class VectorClockModel(BaseModel):
    """Vector clock for maintaining causal ordering."""
    clocks: Dict[str, int] = Field(default_factory=dict)
    
    def increment(self, node_id: str) -> None:
        """Increment the clock for a specific node."""
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1
    
    def update(self, other: 'VectorClockModel') -> None:
        """Update this clock with another clock (take max of each component)."""
        for node_id, clock_value in other.clocks.items():
            self.clocks[node_id] = max(self.clocks.get(node_id, 0), clock_value)
    
    def update_on_receive(self, other: 'VectorClockModel', receiving_node: str) -> None:
        """Update clock when receiving a message from another node."""
        # First update with received clock
        self.update(other)
        # Then increment own clock
        self.increment(receiving_node)
    
    def compare(self, other: 'VectorClockModel') -> str:
        """Compare two vector clocks and return relationship."""
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        
        self_greater = False
        other_greater = False
        
        for node_id in all_nodes:
            self_val = self.clocks.get(node_id, 0)
            other_val = other.clocks.get(node_id, 0)
            
            if self_val > other_val:
                self_greater = True
            elif other_val > self_val:
                other_greater = True
        
        if self_greater and not other_greater:
            return "after"
        elif other_greater and not self_greater:
            return "before"
        elif not self_greater and not other_greater:
            return "equal"
        else:
            return "concurrent"
    
    def is_concurrent_with(self, other: 'VectorClockModel') -> bool:
        """Check if two vector clocks represent concurrent events."""
        return self.compare(other) == "concurrent"
    
    def is_causally_before(self, other: 'VectorClockModel') -> bool:
        """Check if this clock is causally before another."""
        return self.compare(other) == "before"
    
    def is_causally_after(self, other: 'VectorClockModel') -> bool:
        """Check if this clock is causally after another."""
        return self.compare(other) == "after"
    
    def get_max_time(self) -> int:
        """Get the maximum logical time across all nodes."""
        return max(self.clocks.values()) if self.clocks else 0
    
    def copy(self) -> 'VectorClockModel':
        """Create a copy of this vector clock."""
        return VectorClockModel(clocks=self.clocks.copy())
    
    def to_display_string(self) -> str:
        """Convert to human-readable string for UI display."""
        if not self.clocks:
            return "[]"
        sorted_items = sorted(self.clocks.items())
        clock_values = [str(value) for _, value in sorted_items]
        return f"[{', '.join(clock_values)}]"


class FileChunk(BaseModel):
    """Represents a chunk of a file for delta synchronization."""
    index: int
    offset: int
    size: int
    hash: str  # SHA-256 hash of chunk content
    weak_hash: Optional[int] = None  # Rolling hash for rsync-like optimization
    data: Optional[Union[bytes, str]] = None  # Can be bytes or base64 string
    is_new: bool = False  # True if this is a new/modified chunk
    
    @validator('data', pre=True)
    def convert_data(cls, v):
        """Convert data to bytes if it's a string."""
        if v is None:
            return None
        elif isinstance(v, str):
            try:
                # Try to decode from base64 first
                import base64
                return base64.b64decode(v)
            except:
                try:
                    # Try to decode from hex
                    return bytes.fromhex(v)
                except:
                    # If both fail, encode as UTF-8
                    return v.encode('utf-8')
        elif isinstance(v, bytes):
            return v
        else:
            return str(v).encode('utf-8')
    
    class Config:
        arbitrary_types_allowed = True


class ChunkSignature(BaseModel):
    """Signature for a file chunk used in delta synchronization."""
    index: int
    offset: int
    size: int
    weak_hash: int  # Rolling hash (32-bit)
    strong_hash: str  # SHA-256 hash
    
    def matches(self, other: 'ChunkSignature') -> bool:
        """Check if this signature matches another."""
        return (self.size == other.size and 
                self.weak_hash == other.weak_hash and 
                self.strong_hash == other.strong_hash)


class FileDelta(BaseModel):
    """Represents the delta between two file versions."""
    file_id: str
    old_hash: Optional[str] = None
    new_hash: str
    old_size: int = 0
    new_size: int
    chunks_to_add: List[FileChunk] = Field(default_factory=list)  # New/modified chunks
    chunks_to_remove: List[int] = Field(default_factory=list)  # Chunk indices to remove
    chunks_unchanged: List[int] = Field(default_factory=list)  # Unchanged chunk indices
    total_chunks: int = 0
    bandwidth_saved: int = 0  # Bytes saved by not transferring unchanged chunks
    compression_ratio: float = 0.0  # Percentage of data that didn't need transfer
    
    def calculate_efficiency(self) -> Dict[str, float]:
        """Calculate delta sync efficiency metrics."""
        if self.new_size == 0:
            return {"bandwidth_saved_percent": 0.0, "compression_ratio": 0.0}
        
        bandwidth_saved_percent = (self.bandwidth_saved / self.new_size) * 100
        unchanged_chunks = len(self.chunks_unchanged)
        total_chunks = self.total_chunks or (len(self.chunks_to_add) + unchanged_chunks)
        compression_ratio = (unchanged_chunks / total_chunks * 100) if total_chunks > 0 else 0.0
        
        return {
            "bandwidth_saved_percent": bandwidth_saved_percent,
            "compression_ratio": compression_ratio,
            "chunks_reused": unchanged_chunks,
            "chunks_transferred": len(self.chunks_to_add)
        }
    
    class Config:
        arbitrary_types_allowed = True


class DeltaSyncMetrics(BaseModel):
    """Metrics for delta synchronization performance."""
    file_id: str
    original_size: int
    compressed_size: int
    bandwidth_saved: int
    chunks_total: int
    chunks_unchanged: int
    chunks_modified: int
    chunks_new: int
    sync_time: float  # seconds
    throughput: float  # bytes per second
    compression_ratio: float  # percentage
    
    @property
    def efficiency_percent(self) -> float:
        """Calculate overall efficiency percentage."""
        if self.original_size == 0:
            return 0.0
        return (self.bandwidth_saved / self.original_size) * 100


class FileMetadata(BaseModel):
    """Metadata for a file in the system."""
    file_id: str
    name: str
    path: str
    size: int
    hash: str
    created_at: datetime
    modified_at: datetime
    owner_node: str
    version: int = 1
    vector_clock: VectorClockModel = Field(default_factory=VectorClockModel)
    is_deleted: bool = False
    content_type: Optional[str] = None
    
    @validator('file_id', pre=True, always=True)
    def generate_file_id(cls, v, values):
        if not v and 'path' in values and 'owner_node' in values:
            # Generate file_id from path and owner_node
            content = f"{values['owner_node']}:{values['path']}"
            return hashlib.sha256(content.encode()).hexdigest()[:16]
        return v


class FileVersion(BaseModel):
    """Represents a specific version of a file."""
    version_id: str
    file_id: str
    version_number: int
    hash: str
    size: int
    created_at: datetime
    created_by: str
    vector_clock: VectorClockModel
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_current: bool = False


class NodeInfo(BaseModel):
    """Information about a node in the network."""
    node_id: str
    name: str = ""  # Add name field with default value
    address: str
    port: int
    status: NodeStatus = NodeStatus.OFFLINE
    last_seen: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    capabilities: List[str] = Field(default_factory=list)
    watch_directories: List[str] = Field(default_factory=list)
    file_count: int = 0
    total_size: int = 0
    vector_clock: VectorClockModel = Field(default_factory=VectorClockModel)


class SyncEvent(BaseModel):
    """Represents a synchronization event in the system."""
    event_id: str = Field(default_factory=lambda: hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:16])
    event_type: SyncEventType
    node_id: str
    file_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    vector_clock: VectorClockModel = Field(default_factory=VectorClockModel)
    data: Dict[str, Any] = Field(default_factory=dict)
    processed: bool = False


class ConflictInfo(BaseModel):
    """Information about a file conflict."""
    conflict_id: str = Field(default_factory=lambda: hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:16])
    file_id: str
    node1: str
    node2: str
    node1_version: FileVersion
    node2_version: FileVersion
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolution_strategy: Optional[str] = None
    resolved_version_id: Optional[str] = None
    is_resolved: bool = False


class NetworkMetrics(BaseModel):
    """Network performance metrics."""
    node_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    bandwidth_used: int = 0  # bytes
    bandwidth_saved: int = 0  # bytes from delta sync
    sync_time: float = 0.0  # seconds
    file_count: int = 0
    error_count: int = 0
    latency_ms: float = 0.0


# Request/Response Models for API

class RegisterNodeRequest(BaseModel):
    """Request to register a new node."""
    node_id: str
    name: str
    address: str
    port: int
    watch_directories: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)


class RegisterNodeResponse(BaseModel):
    """Response after registering a node."""
    success: bool
    message: str
    node_info: Optional[NodeInfo] = None


class FileUploadRequest(BaseModel):
    """Request to upload a file."""
    file_metadata: FileMetadata
    chunks: List[FileChunk] = Field(default_factory=list)
    vector_clock: VectorClockModel
    use_delta_sync: bool = True
    base_hash: Optional[str] = None  # For delta sync


class FileUploadResponse(BaseModel):
    """Response after uploading a file."""
    success: bool
    message: str
    file_id: str
    version_id: Optional[str] = None
    delta: Optional[FileDelta] = None
    bandwidth_saved: int = 0


class FileDownloadRequest(BaseModel):
    """Request to download a file."""
    file_id: str
    node_id: str
    version_number: Optional[int] = None  # Latest if not specified


class FileDownloadResponse(BaseModel):
    """Response for file download."""
    success: bool
    message: str
    file_metadata: Optional[FileMetadata] = None
    content: Optional[bytes] = None
    
    class Config:
        arbitrary_types_allowed = True


class SyncStatusRequest(BaseModel):
    """Request for synchronization status."""
    node_id: str
    last_sync_time: Optional[datetime] = None


class SyncStatusResponse(BaseModel):
    """Response with synchronization status."""
    success: bool
    pending_events: List[SyncEvent] = Field(default_factory=list)
    conflicts: List[ConflictInfo] = Field(default_factory=list)
    node_status: Dict[str, NodeStatus] = Field(default_factory=dict)


class ConflictResolutionRequest(BaseModel):
    """Request to resolve a conflict."""
    conflict_id: str
    resolution_strategy: str  # "keep_local", "keep_remote", "merge", "manual"
    resolved_content: Optional[bytes] = None
    
    class Config:
        arbitrary_types_allowed = True


class ConflictResolutionResponse(BaseModel):
    """Response after resolving a conflict."""
    success: bool
    message: str
    resolved_version_id: Optional[str] = None


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    node_id: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    nodes_count: int = 0
    files_count: int = 0
    active_conflicts: int = 0


class DeltaSyncRequest(BaseModel):
    """Request for delta synchronization."""
    file_id: str
    current_version: int
    current_chunks: List[FileChunk] = Field(default_factory=list)
    vector_clock: VectorClockModel


class RestoreVersionRequest(BaseModel):
    """Request to restore a file version."""
    node_id: str
    version_id: str 