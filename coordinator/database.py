"""
Database layer for the distributed file synchronization coordinator.
Handles all database operations using SQLite with async support.
"""

import aiosqlite
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from shared.models import (
    NodeInfo, FileMetadata, SyncEvent, ConflictInfo, 
    NodeStatus, SyncEventType, VectorClockModel
)


class DatabaseManager:
    """
    Database manager for the coordinator.
    Handles all persistent storage operations using SQLite.
    """
    
    def __init__(self, db_path: str = "./coordinator.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_initialized = False
        
        # Ensure database directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """Initialize database schema if not exists."""
        if self.db_initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables(db)
            await self._create_indexes(db)
            await db.commit()
        
        self.db_initialized = True
        logging.info("Database initialized successfully")
    
    async def _create_tables(self, db: aiosqlite.Connection) -> None:
        """Create database tables."""
        
        # Nodes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                address TEXT NOT NULL,
                port INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'offline',
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version TEXT DEFAULT '1.0.0',
                capabilities TEXT DEFAULT '[]',
                watch_directories TEXT DEFAULT '[]',
                file_count INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                vector_clock TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Files table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                hash TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                modified_at TIMESTAMP NOT NULL,
                owner_node TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                vector_clock TEXT NOT NULL,
                is_deleted BOOLEAN DEFAULT FALSE,
                content_type TEXT,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (owner_node) REFERENCES nodes (node_id)
            )
        """)
        
        # Events table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                node_id TEXT NOT NULL,
                file_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vector_clock TEXT NOT NULL,
                data TEXT DEFAULT '{}',
                processed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (node_id) REFERENCES nodes (node_id),
                FOREIGN KEY (file_id) REFERENCES files (file_id)
            )
        """)
        
        # Conflicts table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                node1 TEXT NOT NULL,
                node2 TEXT NOT NULL,
                node1_version_data TEXT NOT NULL,
                node2_version_data TEXT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolution_strategy TEXT,
                resolved_version_id TEXT,
                is_resolved BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (file_id) REFERENCES files (file_id),
                FOREIGN KEY (node1) REFERENCES nodes (node_id),
                FOREIGN KEY (node2) REFERENCES nodes (node_id)
            )
        """)
        
        # Network metrics table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS network_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bandwidth_used INTEGER DEFAULT 0,
                bandwidth_saved INTEGER DEFAULT 0,
                sync_time REAL DEFAULT 0.0,
                file_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                latency_ms REAL DEFAULT 0.0,
                FOREIGN KEY (node_id) REFERENCES nodes (node_id)
            )
        """)
    
    async def _create_indexes(self, db: aiosqlite.Connection) -> None:
        """Create database indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes (status)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_last_seen ON nodes (last_seen)",
            "CREATE INDEX IF NOT EXISTS idx_files_owner_node ON files (owner_node)",
            "CREATE INDEX IF NOT EXISTS idx_files_hash ON files (hash)",
            "CREATE INDEX IF NOT EXISTS idx_files_modified_at ON files (modified_at)",
            "CREATE INDEX IF NOT EXISTS idx_events_node_id ON events (node_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_file_id ON events (file_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_events_processed ON events (processed)",
            "CREATE INDEX IF NOT EXISTS idx_conflicts_file_id ON conflicts (file_id)",
            "CREATE INDEX IF NOT EXISTS idx_conflicts_is_resolved ON conflicts (is_resolved)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_node_id ON network_metrics (node_id)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON network_metrics (timestamp)"
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
    
    # Node operations
    
    async def register_node(self, node_info: NodeInfo) -> bool:
        """Register a new node or update existing one."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO nodes 
                    (node_id, address, port, status, last_seen, version, capabilities, 
                     watch_directories, file_count, total_size, vector_clock, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    node_info.node_id,
                    node_info.address,
                    node_info.port,
                    node_info.status.value,
                    node_info.last_seen,
                    node_info.version,
                    json.dumps(node_info.capabilities),
                    json.dumps(node_info.watch_directories),
                    node_info.file_count,
                    node_info.total_size,
                    json.dumps(node_info.vector_clock.model_dump()),
                    datetime.now()
                ))
                await db.commit()
            
            logging.info(f"Registered node {node_info.node_id}")
            return True
        
        except Exception as e:
            logging.error(f"Error registering node {node_info.node_id}: {e}")
            return False
    
    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """Get node information by ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM nodes WHERE node_id = ?", (node_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return self._row_to_node_info(row)
            
            return None
        
        except Exception as e:
            logging.error(f"Error getting node {node_id}: {e}")
            return None
    
    async def get_all_nodes(self) -> List[NodeInfo]:
        """Get all registered nodes."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT * FROM nodes ORDER BY node_id") as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_node_info(row) for row in rows]
        
        except Exception as e:
            logging.error(f"Error getting all nodes: {e}")
            return []
    
    async def update_node_status(self, node_id: str, status: NodeStatus) -> bool:
        """Update node status."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE nodes 
                    SET status = ?, last_seen = ?, updated_at = ?
                    WHERE node_id = ?
                """, (status.value, datetime.now(), datetime.now(), node_id))
                await db.commit()
            
            return True
        
        except Exception as e:
            logging.error(f"Error updating node status for {node_id}: {e}")
            return False
    
    async def get_online_nodes(self) -> List[NodeInfo]:
        """Get all online nodes."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM nodes WHERE status = ? ORDER BY node_id", 
                    (NodeStatus.ONLINE.value,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_node_info(row) for row in rows]
        
        except Exception as e:
            logging.error(f"Error getting online nodes: {e}")
            return []

    async def remove_node(self, node_id: str) -> bool:
        """Remove a node from the database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Remove node from nodes table
                await db.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
                
                # Remove associated events
                await db.execute("DELETE FROM events WHERE node_id = ?", (node_id,))
                
                # Remove from network metrics
                await db.execute("DELETE FROM network_metrics WHERE node_id = ?", (node_id,))
                
                # Remove conflicts involving this node
                await db.execute(
                    "DELETE FROM conflicts WHERE node1 = ? OR node2 = ?", 
                    (node_id, node_id)
                )
                
                await db.commit()
            
            logging.info(f"Removed node {node_id} from database")
            return True
        
        except Exception as e:
            logging.error(f"Error removing node {node_id}: {e}")
            return False
    
    # File operations
    
    async def store_file(self, file_metadata: FileMetadata) -> bool:
        """Store file metadata."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO files 
                    (file_id, name, path, size, hash, created_at, modified_at, 
                     owner_node, version, vector_clock, is_deleted, content_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_metadata.file_id,
                    file_metadata.name,
                    file_metadata.path,
                    file_metadata.size,
                    file_metadata.hash,
                    file_metadata.created_at,
                    file_metadata.modified_at,
                    file_metadata.owner_node,
                    file_metadata.version,
                    json.dumps(file_metadata.vector_clock.model_dump()),
                    file_metadata.is_deleted,
                    file_metadata.content_type,
                    json.dumps({})  # Additional metadata
                ))
                await db.commit()
            
            logging.info(f"Stored file {file_metadata.file_id}")
            return True
        
        except Exception as e:
            logging.error(f"Error storing file {file_metadata.file_id}: {e}")
            return False
    
    async def get_file(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata by ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM files WHERE file_id = ?", (file_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return self._row_to_file_metadata(row)
            
            return None
        
        except Exception as e:
            logging.error(f"Error getting file {file_id}: {e}")
            return None
    
    async def get_files_by_node(self, node_id: str) -> List[FileMetadata]:
        """Get all files owned by a specific node."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM files WHERE owner_node = ? AND is_deleted = FALSE ORDER BY modified_at DESC", 
                    (node_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_file_metadata(row) for row in rows]
        
        except Exception as e:
            logging.error(f"Error getting files for node {node_id}: {e}")
            return []
    
    async def get_all_files(self, include_deleted: bool = False) -> List[FileMetadata]:
        """Get all files."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if include_deleted:
                    query = "SELECT * FROM files ORDER BY modified_at DESC"
                    params = ()
                else:
                    query = "SELECT * FROM files WHERE is_deleted = FALSE ORDER BY modified_at DESC"
                    params = ()
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_file_metadata(row) for row in rows]
        
        except Exception as e:
            logging.error(f"Error getting all files: {e}")
            return []
    
    async def delete_file(self, file_id: str) -> bool:
        """Mark file as deleted."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE files SET is_deleted = TRUE WHERE file_id = ?", 
                    (file_id,)
                )
                await db.commit()
            
            return True
        
        except Exception as e:
            logging.error(f"Error deleting file {file_id}: {e}")
            return False
    
    # Event operations
    
    async def record_event(self, event: SyncEvent) -> bool:
        """Record a synchronization event."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO events 
                    (event_id, event_type, node_id, file_id, timestamp, vector_clock, data, processed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.event_type.value,
                    event.node_id,
                    event.file_id,
                    event.timestamp,
                    json.dumps(event.vector_clock.model_dump()),
                    json.dumps(event.data),
                    event.processed
                ))
                await db.commit()
            
            logging.debug(f"Recorded event {event.event_id}")
            return True
        
        except Exception as e:
            logging.error(f"Error recording event {event.event_id}: {e}")
            return False
    
    async def get_events_by_node(self, node_id: str, limit: int = 100) -> List[SyncEvent]:
        """Get events for a specific node."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT * FROM events 
                    WHERE node_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (node_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_sync_event(row) for row in rows]
        
        except Exception as e:
            logging.error(f"Error getting events for node {node_id}: {e}")
            return []
    
    async def get_unprocessed_events(self, limit: int = 100) -> List[SyncEvent]:
        """Get unprocessed events."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT * FROM events 
                    WHERE processed = FALSE 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_sync_event(row) for row in rows]
        
        except Exception as e:
            logging.error(f"Error getting unprocessed events: {e}")
            return []
    
    async def get_recent_events(self, limit: int = 100) -> List[SyncEvent]:
        """Get recent events (both processed and unprocessed)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT * FROM events 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_sync_event(row) for row in rows]
        
        except Exception as e:
            logging.error(f"Error getting recent events: {e}")
            return []
    
    async def mark_event_processed(self, event_id: str) -> bool:
        """Mark an event as processed."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE events SET processed = TRUE WHERE event_id = ?", 
                    (event_id,)
                )
                await db.commit()
            
            return True
        
        except Exception as e:
            logging.error(f"Error marking event {event_id} as processed: {e}")
            return False
    
    # Conflict operations
    
    async def record_conflict(self, conflict: ConflictInfo) -> bool:
        """Record a file conflict."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO conflicts 
                    (conflict_id, file_id, node1, node2, node1_version_data, node2_version_data,
                     detected_at, resolved_at, resolution_strategy, resolved_version_id, is_resolved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conflict.conflict_id,
                    conflict.file_id,
                    conflict.node1,
                    conflict.node2,
                    json.dumps(conflict.node1_version.model_dump()),
                    json.dumps(conflict.node2_version.model_dump()),
                    conflict.detected_at,
                    conflict.resolved_at,
                    conflict.resolution_strategy,
                    conflict.resolved_version_id,
                    conflict.is_resolved
                ))
                await db.commit()
            
            logging.info(f"Recorded conflict {conflict.conflict_id}")
            return True
        
        except Exception as e:
            logging.error(f"Error recording conflict {conflict.conflict_id}: {e}")
            return False
    
    async def get_conflict(self, conflict_id: str) -> Optional[ConflictInfo]:
        """Get conflict information by ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM conflicts WHERE conflict_id = ?", (conflict_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return await self._row_to_conflict_info(row)
            
            return None
        
        except Exception as e:
            logging.error(f"Error getting conflict {conflict_id}: {e}")
            return None
    
    async def get_unresolved_conflicts(self) -> List[ConflictInfo]:
        """Get all unresolved conflicts."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT * FROM conflicts 
                    WHERE is_resolved = FALSE 
                    ORDER BY detected_at DESC
                """) as cursor:
                    rows = await cursor.fetchall()
                    conflicts = []
                    for row in rows:
                        conflict = await self._row_to_conflict_info(row)
                        if conflict:
                            conflicts.append(conflict)
                    return conflicts
        
        except Exception as e:
            logging.error(f"Error getting unresolved conflicts: {e}")
            return []
    
    async def resolve_conflict(self, conflict_id: str, resolution_strategy: str, 
                             resolved_version_id: str) -> bool:
        """Mark a conflict as resolved."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE conflicts 
                    SET is_resolved = TRUE, resolved_at = ?, resolution_strategy = ?, resolved_version_id = ?
                    WHERE conflict_id = ?
                """, (datetime.now(), resolution_strategy, resolved_version_id, conflict_id))
                await db.commit()
            
            logging.info(f"Resolved conflict {conflict_id}")
            return True
        
        except Exception as e:
            logging.error(f"Error resolving conflict {conflict_id}: {e}")
            return False
    
    # Statistics and cleanup
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                
                # Node statistics
                async with db.execute("SELECT COUNT(*) FROM nodes") as cursor:
                    stats['total_nodes'] = (await cursor.fetchone())[0]
                
                async with db.execute("SELECT COUNT(*) FROM nodes WHERE status = ?", (NodeStatus.ONLINE.value,)) as cursor:
                    stats['online_nodes'] = (await cursor.fetchone())[0]
                
                # File statistics
                async with db.execute("SELECT COUNT(*) FROM files WHERE is_deleted = FALSE") as cursor:
                    stats['total_files'] = (await cursor.fetchone())[0]
                
                async with db.execute("SELECT SUM(size) FROM files WHERE is_deleted = FALSE") as cursor:
                    result = await cursor.fetchone()
                    stats['total_file_size'] = result[0] if result[0] else 0
                
                # Event statistics
                async with db.execute("SELECT COUNT(*) FROM events") as cursor:
                    stats['total_events'] = (await cursor.fetchone())[0]
                
                async with db.execute("SELECT COUNT(*) FROM events WHERE processed = FALSE") as cursor:
                    stats['unprocessed_events'] = (await cursor.fetchone())[0]
                
                # Conflict statistics
                async with db.execute("SELECT COUNT(*) FROM conflicts") as cursor:
                    stats['total_conflicts'] = (await cursor.fetchone())[0]
                
                async with db.execute("SELECT COUNT(*) FROM conflicts WHERE is_resolved = FALSE") as cursor:
                    stats['unresolved_conflicts'] = (await cursor.fetchone())[0]
                
                return stats
        
        except Exception as e:
            logging.error(f"Error getting statistics: {e}")
            return {}
    
    async def cleanup_old_events(self, days_to_keep: int = 30) -> int:
        """Clean up old processed events."""
        try:
            cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    DELETE FROM events 
                    WHERE processed = TRUE AND timestamp < ?
                """, (datetime.fromtimestamp(cutoff_date),)) as cursor:
                    deleted_count = cursor.rowcount
                
                await db.commit()
                
                logging.info(f"Cleaned up {deleted_count} old events")
                return deleted_count
        
        except Exception as e:
            logging.error(f"Error cleaning up old events: {e}")
            return 0
    
    # Helper methods for row conversion
    
    def _row_to_node_info(self, row) -> NodeInfo:
        """Convert database row to NodeInfo object."""
        return NodeInfo(
            node_id=row[0],
            address=row[1],
            port=row[2],
            status=NodeStatus(row[3]),
            last_seen=datetime.fromisoformat(row[4]) if row[4] else datetime.now(),
            version=row[5],
            capabilities=json.loads(row[6]) if row[6] else [],
            watch_directories=json.loads(row[7]) if row[7] else [],
            file_count=row[8],
            total_size=row[9],
            vector_clock=VectorClockModel(**(json.loads(row[10]) if row[10] else {}))
        )
    
    def _row_to_file_metadata(self, row) -> FileMetadata:
        """Convert database row to FileMetadata object."""
        return FileMetadata(
            file_id=row[0],
            name=row[1],
            path=row[2],
            size=row[3],
            hash=row[4],
            created_at=datetime.fromisoformat(row[5]),
            modified_at=datetime.fromisoformat(row[6]),
            owner_node=row[7],
            version=row[8],
            vector_clock=VectorClockModel(**(json.loads(row[9]))),
            is_deleted=bool(row[10]),
            content_type=row[11]
        )
    
    def _row_to_sync_event(self, row) -> SyncEvent:
        """Convert database row to SyncEvent object."""
        return SyncEvent(
            event_id=row[0],
            event_type=SyncEventType(row[1]),
            node_id=row[2],
            file_id=row[3],
            timestamp=datetime.fromisoformat(row[4]),
            vector_clock=VectorClockModel(**(json.loads(row[5]))),
            data=json.loads(row[6]) if row[6] else {},
            processed=bool(row[7])
        )
    
    async def _row_to_conflict_info(self, row) -> Optional[ConflictInfo]:
        """Convert database row to ConflictInfo object."""
        try:
            # Note: This is simplified - in a real implementation you'd need to 
            # properly reconstruct FileVersion objects from the stored JSON data
            from shared.models import FileVersion
            
            node1_version_data = json.loads(row[4])
            node2_version_data = json.loads(row[5])
            
            # This is a simplified version - you'd need proper FileVersion reconstruction
            node1_version = FileVersion(**node1_version_data)
            node2_version = FileVersion(**node2_version_data)
            
            return ConflictInfo(
                conflict_id=row[0],
                file_id=row[1],
                node1=row[2],
                node2=row[3],
                node1_version=node1_version,
                node2_version=node2_version,
                detected_at=datetime.fromisoformat(row[6]),
                resolved_at=datetime.fromisoformat(row[7]) if row[7] else None,
                resolution_strategy=row[8],
                resolved_version_id=row[9],
                is_resolved=bool(row[10])
            )
        except Exception as e:
            logging.error(f"Error converting row to conflict info: {e}")
            return None 