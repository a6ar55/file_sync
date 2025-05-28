"""
File version manager for the distributed file synchronization system.
Handles file versioning, history tracking, and conflict resolution.
"""

import json
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from shared.models import FileVersion, FileMetadata, VectorClockModel
from shared.utils import calculate_content_hash, calculate_file_hash, ensure_directory, format_bytes, generate_unique_id


@dataclass
class VersionStats:
    """Statistics for file versions."""
    total_versions: int
    total_size: int
    oldest_version: Optional[datetime]
    newest_version: Optional[datetime]
    current_version: Optional[str]


class FileVersionManager:
    """
    Manages file versions, history, and metadata.
    Provides version control functionality for the distributed file sync system.
    """
    
    def __init__(self, storage_path: str = "./versions"):
        """
        Initialize file version manager.
        
        Args:
            storage_path: Directory to store file versions
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories for organization
        self.versions_dir = self.storage_path / "data"
        self.metadata_dir = self.storage_path / "metadata"
        
        self.versions_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)
        
        # In-memory cache for quick access
        self.version_cache: Dict[str, FileVersion] = {}
        self.file_metadata_cache: Dict[str, FileMetadata] = {}
        
        # Load existing metadata
        self._load_metadata_cache()
    
    def create_version(self, file_id: str, content: bytes, created_by: str, 
                      vector_clock: VectorClockModel, metadata: Dict[str, Any] = None) -> FileVersion:
        """
        Create a new version of a file.
        
        Args:
            file_id: Unique file identifier
            content: File content as bytes
            created_by: Node ID that created this version
            vector_clock: Vector clock for this version
            metadata: Optional additional metadata
            
        Returns:
            Created FileVersion object
        """
        try:
            # Generate version ID and calculate hash
            version_id = generate_unique_id(f"v_{file_id}")
            content_hash = calculate_content_hash(content)
            
            # Determine version number
            existing_versions = self.get_file_versions(file_id)
            version_number = len(existing_versions) + 1
            
            # Create version object
            version = FileVersion(
                version_id=version_id,
                file_id=file_id,
                version_number=version_number,
                hash=content_hash,
                size=len(content),
                created_at=datetime.now(),
                created_by=created_by,
                vector_clock=vector_clock,
                metadata=metadata or {},
                is_current=True  # Will be set to False for previous versions
            )
            
            # Mark previous versions as not current
            for existing_version in existing_versions:
                existing_version.is_current = False
                self._save_version_metadata(existing_version)
            
            # Store version data and metadata
            self._store_version_data(version_id, content)
            self._save_version_metadata(version)
            
            # Update cache
            self.version_cache[version_id] = version
            
            logging.info(f"Created version {version_id} for file {file_id}")
            return version
        
        except Exception as e:
            logging.error(f"Error creating version for file {file_id}: {e}")
            raise
    
    def get_version(self, version_id: str) -> Optional[FileVersion]:
        """
        Get a specific file version.
        
        Args:
            version_id: Version identifier
            
        Returns:
            FileVersion object or None if not found
        """
        # Check cache first
        if version_id in self.version_cache:
            return self.version_cache[version_id]
        
        # Load from disk
        metadata_path = self.metadata_dir / f"{version_id}.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    data = json.load(f)
                
                version = FileVersion(
                    version_id=data["version_id"],
                    file_id=data["file_id"],
                    version_number=data["version_number"],
                    hash=data["hash"],
                    size=data["size"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    created_by=data["created_by"],
                    vector_clock=VectorClockModel(**data["vector_clock"]),
                    metadata=data.get("metadata", {}),
                    is_current=data.get("is_current", False)
                )
                
                # Cache for future access
                self.version_cache[version_id] = version
                return version
            
            except Exception as e:
                logging.error(f"Error loading version {version_id}: {e}")
        
        return None
    
    def get_version_content(self, version_id: str) -> Optional[bytes]:
        """
        Get the content of a specific version.
        
        Args:
            version_id: Version identifier
            
        Returns:
            File content as bytes or None if not found
        """
        version_path = self.versions_dir / f"{version_id}.data"
        if version_path.exists():
            try:
                with open(version_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                logging.error(f"Error reading version content {version_id}: {e}")
        
        return None
    
    def get_file_versions(self, file_id: str) -> List[FileVersion]:
        """
        Get all versions of a specific file.
        
        Args:
            file_id: File identifier
            
        Returns:
            List of FileVersion objects sorted by version number
        """
        versions = []
        
        # Search through metadata files
        for metadata_file in self.metadata_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                
                if data.get("file_id") == file_id:
                    version = FileVersion(
                        version_id=data["version_id"],
                        file_id=data["file_id"],
                        version_number=data["version_number"],
                        hash=data["hash"],
                        size=data["size"],
                        created_at=datetime.fromisoformat(data["created_at"]),
                        created_by=data["created_by"],
                        vector_clock=VectorClockModel(**data["vector_clock"]),
                        metadata=data.get("metadata", {}),
                        is_current=data.get("is_current", False)
                    )
                    versions.append(version)
            
            except Exception as e:
                logging.error(f"Error reading metadata file {metadata_file}: {e}")
        
        # Sort by version number
        return sorted(versions, key=lambda v: v.version_number)
    
    def get_current_version(self, file_id: str) -> Optional[FileVersion]:
        """
        Get the current (latest) version of a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            Current FileVersion or None if file doesn't exist
        """
        versions = self.get_file_versions(file_id)
        current_versions = [v for v in versions if v.is_current]
        
        if current_versions:
            return current_versions[0]
        elif versions:
            # Fallback to latest version if none marked as current
            return versions[-1]
        
        return None
    
    def restore_version(self, version_id: str, target_path: str) -> bool:
        """
        Restore a specific version to a target file path.
        
        Args:
            version_id: Version to restore
            target_path: Target file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            content = self.get_version_content(version_id)
            if content is None:
                logging.error(f"Version {version_id} content not found")
                return False
            
            # Ensure target directory exists
            ensure_directory(os.path.dirname(target_path))
            
            # Write content to target file
            with open(target_path, 'wb') as f:
                f.write(content)
            
            logging.info(f"Restored version {version_id} to {target_path}")
            return True
        
        except Exception as e:
            logging.error(f"Error restoring version {version_id}: {e}")
            return False
    
    def delete_version(self, version_id: str) -> bool:
        """
        Delete a specific version.
        
        Args:
            version_id: Version to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get version info
            version = self.get_version(version_id)
            if not version:
                return False
            
            # Don't allow deleting the current version if it's the only one
            file_versions = self.get_file_versions(version.file_id)
            if len(file_versions) == 1 and version.is_current:
                logging.warning(f"Cannot delete the only version {version_id}")
                return False
            
            # Delete data and metadata files
            data_path = self.versions_dir / f"{version_id}.data"
            metadata_path = self.metadata_dir / f"{version_id}.json"
            
            if data_path.exists():
                os.remove(data_path)
            if metadata_path.exists():
                os.remove(metadata_path)
            
            # Remove from cache
            if version_id in self.version_cache:
                del self.version_cache[version_id]
            
            # If this was the current version, mark the latest remaining version as current
            if version.is_current:
                remaining_versions = [v for v in file_versions if v.version_id != version_id]
                if remaining_versions:
                    latest_version = max(remaining_versions, key=lambda v: v.version_number)
                    latest_version.is_current = True
                    self._save_version_metadata(latest_version)
            
            logging.info(f"Deleted version {version_id}")
            return True
        
        except Exception as e:
            logging.error(f"Error deleting version {version_id}: {e}")
            return False
    
    def merge_versions(self, version1_id: str, version2_id: str, merge_strategy: str = "latest") -> Optional[FileVersion]:
        """
        Merge two versions using the specified strategy.
        
        Args:
            version1_id: First version ID
            version2_id: Second version ID
            merge_strategy: Strategy for merging ("latest", "largest", "manual")
            
        Returns:
            Merged FileVersion or None if merge failed
        """
        try:
            version1 = self.get_version(version1_id)
            version2 = self.get_version(version2_id)
            
            if not version1 or not version2:
                logging.error("One or both versions not found for merging")
                return None
            
            if version1.file_id != version2.file_id:
                logging.error("Cannot merge versions from different files")
                return None
            
            # Apply merge strategy
            if merge_strategy == "latest":
                winner = version1 if version1.created_at > version2.created_at else version2
            elif merge_strategy == "largest":
                winner = version1 if version1.size > version2.size else version2
            else:
                # For manual merging, default to version1
                winner = version1
            
            # Get winner's content
            content = self.get_version_content(winner.version_id)
            if content is None:
                logging.error(f"Cannot retrieve content for winning version {winner.version_id}")
                return None
            
            # Create merged vector clock (take max of each component)
            merged_clock = version1.vector_clock.copy()
            merged_clock.update(version2.vector_clock)
            
            # Create new merged version
            merged_version = self.create_version(
                file_id=version1.file_id,
                content=content,
                created_by=f"merge_{version1.created_by}_{version2.created_by}",
                vector_clock=merged_clock,
                metadata={
                    "merged_from": [version1_id, version2_id],
                    "merge_strategy": merge_strategy,
                    "merge_timestamp": datetime.now().isoformat()
                }
            )
            
            logging.info(f"Merged versions {version1_id} and {version2_id} into {merged_version.version_id}")
            return merged_version
        
        except Exception as e:
            logging.error(f"Error merging versions {version1_id} and {version2_id}: {e}")
            return None
    
    def get_version_diff(self, version1_id: str, version2_id: str) -> Dict[str, Any]:
        """
        Get differences between two versions.
        
        Args:
            version1_id: First version ID
            version2_id: Second version ID
            
        Returns:
            Dictionary with diff information
        """
        try:
            version1 = self.get_version(version1_id)
            version2 = self.get_version(version2_id)
            
            if not version1 or not version2:
                return {"error": "One or both versions not found"}
            
            content1 = self.get_version_content(version1_id)
            content2 = self.get_version_content(version2_id)
            
            if content1 is None or content2 is None:
                return {"error": "Cannot retrieve version content"}
            
            # Basic diff information
            diff_info = {
                "version1": {
                    "id": version1_id,
                    "size": version1.size,
                    "hash": version1.hash,
                    "created_at": version1.created_at.isoformat()
                },
                "version2": {
                    "id": version2_id,
                    "size": version2.size,
                    "hash": version2.hash,
                    "created_at": version2.created_at.isoformat()
                },
                "size_difference": version2.size - version1.size,
                "hash_changed": version1.hash != version2.hash,
                "content_identical": content1 == content2
            }
            
            # Vector clock comparison
            clock_comparison = version1.vector_clock.compare(version2.vector_clock)
            diff_info["vector_clock_relationship"] = clock_comparison
            
            return diff_info
        
        except Exception as e:
            logging.error(f"Error getting diff between {version1_id} and {version2_id}: {e}")
            return {"error": str(e)}
    
    def get_file_statistics(self, file_id: str) -> VersionStats:
        """
        Get statistics for all versions of a file.
        
        Args:
            file_id: File identifier
            
        Returns:
            VersionStats object
        """
        versions = self.get_file_versions(file_id)
        
        if not versions:
            return VersionStats(
                total_versions=0,
                total_size=0,
                oldest_version=None,
                newest_version=None,
                current_version=None
            )
        
        total_size = sum(v.size for v in versions)
        creation_dates = [v.created_at for v in versions]
        current_version = next((v.version_id for v in versions if v.is_current), None)
        
        return VersionStats(
            total_versions=len(versions),
            total_size=total_size,
            oldest_version=min(creation_dates),
            newest_version=max(creation_dates),
            current_version=current_version
        )
    
    def cleanup_old_versions(self, file_id: str, keep_versions: int = 10) -> int:
        """
        Clean up old versions, keeping only the specified number.
        
        Args:
            file_id: File identifier
            keep_versions: Number of versions to keep
            
        Returns:
            Number of versions deleted
        """
        try:
            versions = self.get_file_versions(file_id)
            
            if len(versions) <= keep_versions:
                return 0
            
            # Sort by version number and keep the latest ones
            versions_to_delete = versions[:-keep_versions]
            deleted_count = 0
            
            for version in versions_to_delete:
                # Don't delete the current version
                if not version.is_current and self.delete_version(version.version_id):
                    deleted_count += 1
            
            logging.info(f"Cleaned up {deleted_count} old versions for file {file_id}")
            return deleted_count
        
        except Exception as e:
            logging.error(f"Error cleaning up versions for file {file_id}: {e}")
            return 0
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get overall storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            total_versions = 0
            total_size = 0
            files_tracked = set()
            
            for metadata_file in self.metadata_dir.glob("*.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        data = json.load(f)
                    
                    total_versions += 1
                    total_size += data.get("size", 0)
                    files_tracked.add(data.get("file_id"))
                
                except Exception:
                    continue
            
            return {
                "total_versions": total_versions,
                "total_files": len(files_tracked),
                "total_size": total_size,
                "total_size_formatted": format_bytes(total_size),
                "storage_path": str(self.storage_path),
                "average_file_size": total_size // total_versions if total_versions > 0 else 0
            }
        
        except Exception as e:
            logging.error(f"Error getting storage statistics: {e}")
            return {}
    
    def _store_version_data(self, version_id: str, content: bytes) -> None:
        """Store version data to disk."""
        data_path = self.versions_dir / f"{version_id}.data"
        with open(data_path, 'wb') as f:
            f.write(content)
    
    def _save_version_metadata(self, version: FileVersion) -> None:
        """Save version metadata to disk."""
        metadata_path = self.metadata_dir / f"{version.version_id}.json"
        
        metadata = {
            "version_id": version.version_id,
            "file_id": version.file_id,
            "version_number": version.version_number,
            "hash": version.hash,
            "size": version.size,
            "created_at": version.created_at.isoformat(),
            "created_by": version.created_by,
            "vector_clock": version.vector_clock.dict(),
            "metadata": version.metadata,
            "is_current": version.is_current
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_metadata_cache(self) -> None:
        """Load metadata into cache on startup."""
        try:
            for metadata_file in self.metadata_dir.glob("*.json"):
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                
                version = FileVersion(
                    version_id=data["version_id"],
                    file_id=data["file_id"],
                    version_number=data["version_number"],
                    hash=data["hash"],
                    size=data["size"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    created_by=data["created_by"],
                    vector_clock=VectorClockModel(**data["vector_clock"]),
                    metadata=data.get("metadata", {}),
                    is_current=data.get("is_current", False)
                )
                
                self.version_cache[version.version_id] = version
            
            logging.info(f"Loaded {len(self.version_cache)} versions into cache")
        
        except Exception as e:
            logging.error(f"Error loading metadata cache: {e}") 