"""
Delta synchronization engine for efficient file transfers.
Implements file chunking, rolling hash, and delta generation for bandwidth optimization.
"""

import hashlib
import os
import logging
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass
from pathlib import Path

from shared.utils import (
    calculate_content_hash, 
    get_content_chunks, 
    rolling_hash,
    find_chunk_boundaries,
    format_bytes
)


@dataclass
class ChunkSignature:
    """Signature of a file chunk for delta synchronization."""
    index: int
    offset: int
    size: int
    weak_hash: int    # Rolling hash for quick comparison
    strong_hash: str  # SHA-256 for collision detection
    

@dataclass
class DeltaOperation:
    """Represents a delta operation (add, copy, or delete)."""
    operation: str  # "add", "copy", "delete"
    offset: int
    size: int
    data: Optional[bytes] = None
    source_offset: Optional[int] = None


class DeltaSync:
    """
    Delta synchronization engine that minimizes bandwidth usage
    by transferring only the differences between file versions.
    """
    
    def __init__(self, chunk_size: int = 4096):
        """
        Initialize delta sync engine.
        
        Args:
            chunk_size: Target size for file chunks in bytes
        """
        self.chunk_size = chunk_size
        self.window_size = min(64, chunk_size // 4)
        self.stats = {
            "files_processed": 0,
            "total_original_size": 0,
            "total_delta_size": 0,
            "bandwidth_saved": 0
        }
    
    def create_signature(self, content: bytes) -> List[ChunkSignature]:
        """
        Create signature for file content using chunks.
        
        Args:
            content: File content as bytes
            
        Returns:
            List of chunk signatures
        """
        if not content:
            return []
        
        signatures = []
        boundaries = find_chunk_boundaries(content, self.chunk_size)
        
        offset = 0
        for i, boundary in enumerate(boundaries):
            chunk_data = content[offset:boundary]
            if not chunk_data:
                break
            
            weak_hash = rolling_hash(chunk_data, self.window_size)
            strong_hash = hashlib.sha256(chunk_data).hexdigest()
            
            signature = ChunkSignature(
                index=i,
                offset=offset,
                size=len(chunk_data),
                weak_hash=weak_hash,
                strong_hash=strong_hash
            )
            signatures.append(signature)
            offset = boundary
        
        return signatures
    
    def create_signature_from_file(self, file_path: str) -> List[ChunkSignature]:
        """
        Create signature for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of chunk signatures
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return self.create_signature(content)
        except Exception as e:
            logging.error(f"Error creating signature for {file_path}: {e}")
            return []
    
    def generate_delta(self, old_content: bytes, new_content: bytes) -> List[DeltaOperation]:
        """
        Generate delta operations to transform old content to new content.
        
        Args:
            old_content: Original file content
            new_content: New file content
            
        Returns:
            List of delta operations
        """
        if not old_content:
            # Entire new file is an addition
            return [DeltaOperation(
                operation="add",
                offset=0,
                size=len(new_content),
                data=new_content
            )]
        
        if not new_content:
            # Entire old file is deleted
            return [DeltaOperation(
                operation="delete",
                offset=0,
                size=len(old_content)
            )]
        
        # Create signatures for old content
        old_signatures = self.create_signature(old_content)
        old_sig_map = {sig.strong_hash: sig for sig in old_signatures}
        
        # Generate delta operations
        operations = []
        new_boundaries = find_chunk_boundaries(new_content, self.chunk_size)
        
        new_offset = 0
        for boundary in new_boundaries:
            new_chunk = new_content[new_offset:boundary]
            if not new_chunk:
                break
            
            new_chunk_hash = hashlib.sha256(new_chunk).hexdigest()
            
            if new_chunk_hash in old_sig_map:
                # Chunk exists in old content - copy operation
                old_sig = old_sig_map[new_chunk_hash]
                operations.append(DeltaOperation(
                    operation="copy",
                    offset=new_offset,
                    size=len(new_chunk),
                    source_offset=old_sig.offset
                ))
            else:
                # New chunk - add operation
                operations.append(DeltaOperation(
                    operation="add",
                    offset=new_offset,
                    size=len(new_chunk),
                    data=new_chunk
                ))
            
            new_offset = boundary
        
        return operations
    
    def apply_delta(self, old_content: bytes, delta_ops: List[DeltaOperation]) -> bytes:
        """
        Apply delta operations to reconstruct new content.
        
        Args:
            old_content: Original file content
            delta_ops: List of delta operations
            
        Returns:
            Reconstructed file content
        """
        result = bytearray()
        
        for op in delta_ops:
            if op.operation == "add":
                if op.data:
                    result.extend(op.data)
            elif op.operation == "copy":
                if op.source_offset is not None and old_content:
                    end_offset = op.source_offset + op.size
                    chunk = old_content[op.source_offset:end_offset]
                    result.extend(chunk)
            # Delete operations are implicitly handled by not copying
        
        return bytes(result)
    
    def calculate_delta_size(self, delta_ops: List[DeltaOperation]) -> int:
        """
        Calculate the total size of delta operations.
        
        Args:
            delta_ops: List of delta operations
            
        Returns:
            Total size in bytes
        """
        total_size = 0
        for op in delta_ops:
            if op.operation == "add" and op.data:
                total_size += len(op.data)
            # Copy and delete operations don't contribute to transfer size
            total_size += 32  # Overhead for operation metadata
        
        return total_size
    
    def optimize_delta(self, delta_ops: List[DeltaOperation]) -> List[DeltaOperation]:
        """
        Optimize delta operations by merging adjacent operations.
        
        Args:
            delta_ops: List of delta operations
            
        Returns:
            Optimized list of delta operations
        """
        if not delta_ops:
            return []
        
        optimized = []
        current_op = delta_ops[0]
        
        for next_op in delta_ops[1:]:
            # Try to merge adjacent add operations
            if (current_op.operation == "add" and 
                next_op.operation == "add" and 
                current_op.offset + current_op.size == next_op.offset):
                
                # Merge the operations
                merged_data = (current_op.data or b"") + (next_op.data or b"")
                current_op = DeltaOperation(
                    operation="add",
                    offset=current_op.offset,
                    size=current_op.size + next_op.size,
                    data=merged_data
                )
            else:
                optimized.append(current_op)
                current_op = next_op
        
        optimized.append(current_op)
        return optimized
    
    def create_file_delta(self, old_file_path: str, new_file_path: str) -> Dict[str, Any]:
        """
        Create delta between two files.
        
        Args:
            old_file_path: Path to the old file
            new_file_path: Path to the new file
            
        Returns:
            Dictionary containing delta information
        """
        try:
            # Read file contents
            old_content = b""
            if os.path.exists(old_file_path):
                with open(old_file_path, 'rb') as f:
                    old_content = f.read()
            
            with open(new_file_path, 'rb') as f:
                new_content = f.read()
            
            return self.create_content_delta(old_content, new_content)
        
        except Exception as e:
            logging.error(f"Error creating file delta: {e}")
            return {
                "success": False,
                "error": str(e),
                "operations": [],
                "delta_size": 0,
                "original_size": 0,
                "bandwidth_saved": 0
            }
    
    def create_content_delta(self, old_content: bytes, new_content: bytes) -> Dict[str, Any]:
        """
        Create delta between two content buffers.
        
        Args:
            old_content: Original content
            new_content: New content
            
        Returns:
            Dictionary containing delta information
        """
        try:
            # Generate delta operations
            delta_ops = self.generate_delta(old_content, new_content)
            optimized_ops = self.optimize_delta(delta_ops)
            
            # Calculate sizes and savings
            original_size = len(new_content)
            delta_size = self.calculate_delta_size(optimized_ops)
            bandwidth_saved = max(0, original_size - delta_size)
            
            # Update statistics
            self.stats["files_processed"] += 1
            self.stats["total_original_size"] += original_size
            self.stats["total_delta_size"] += delta_size
            self.stats["bandwidth_saved"] += bandwidth_saved
            
            # Convert operations to serializable format
            serializable_ops = []
            for op in optimized_ops:
                op_dict = {
                    "operation": op.operation,
                    "offset": op.offset,
                    "size": op.size
                }
                if op.data is not None:
                    op_dict["data"] = op.data.hex()  # Convert to hex string
                if op.source_offset is not None:
                    op_dict["source_offset"] = op.source_offset
                serializable_ops.append(op_dict)
            
            return {
                "success": True,
                "operations": serializable_ops,
                "delta_size": delta_size,
                "original_size": original_size,
                "bandwidth_saved": bandwidth_saved,
                "compression_ratio": (bandwidth_saved / original_size * 100) if original_size > 0 else 0,
                "old_hash": calculate_content_hash(old_content),
                "new_hash": calculate_content_hash(new_content)
            }
        
        except Exception as e:
            logging.error(f"Error creating content delta: {e}")
            return {
                "success": False,
                "error": str(e),
                "operations": [],
                "delta_size": 0,
                "original_size": len(new_content),
                "bandwidth_saved": 0
            }
    
    def reconstruct_from_delta(self, old_content: bytes, delta_info: Dict[str, Any]) -> bytes:
        """
        Reconstruct content from delta information.
        
        Args:
            old_content: Original content
            delta_info: Delta information dictionary
            
        Returns:
            Reconstructed content
        """
        try:
            if not delta_info.get("success", False):
                raise ValueError("Invalid delta information")
            
            # Convert serialized operations back to DeltaOperation objects
            operations = []
            for op_dict in delta_info.get("operations", []):
                op = DeltaOperation(
                    operation=op_dict["operation"],
                    offset=op_dict["offset"],
                    size=op_dict["size"]
                )
                
                if "data" in op_dict:
                    op.data = bytes.fromhex(op_dict["data"])
                if "source_offset" in op_dict:
                    op.source_offset = op_dict["source_offset"]
                
                operations.append(op)
            
            # Apply delta operations
            result = self.apply_delta(old_content, operations)
            
            # Verify hash if provided
            if "new_hash" in delta_info:
                result_hash = calculate_content_hash(result)
                if result_hash != delta_info["new_hash"]:
                    raise ValueError("Hash verification failed after delta reconstruction")
            
            return result
        
        except Exception as e:
            logging.error(f"Error reconstructing from delta: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get delta sync statistics.
        
        Returns:
            Dictionary with performance statistics
        """
        total_original = self.stats["total_original_size"]
        total_delta = self.stats["total_delta_size"]
        
        return {
            "files_processed": self.stats["files_processed"],
            "total_original_size": total_original,
            "total_original_size_formatted": format_bytes(total_original),
            "total_delta_size": total_delta,
            "total_delta_size_formatted": format_bytes(total_delta),
            "bandwidth_saved": self.stats["bandwidth_saved"],
            "bandwidth_saved_formatted": format_bytes(self.stats["bandwidth_saved"]),
            "compression_ratio": (self.stats["bandwidth_saved"] / total_original * 100) if total_original > 0 else 0,
            "average_compression": (total_delta / total_original * 100) if total_original > 0 else 100
        }
    
    def reset_statistics(self):
        """Reset delta sync statistics."""
        self.stats = {
            "files_processed": 0,
            "total_original_size": 0,
            "total_delta_size": 0,
            "bandwidth_saved": 0
        }


class ChunkStore:
    """
    Store for managing file chunks and their metadata.
    Used for efficient chunk-based synchronization.
    """
    
    def __init__(self, storage_path: str = "./chunks"):
        """
        Initialize chunk store.
        
        Args:
            storage_path: Directory to store chunks
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.chunk_index: Dict[str, Dict] = {}  # hash -> chunk info
    
    def store_chunk(self, chunk_hash: str, chunk_data: bytes, metadata: Dict = None) -> bool:
        """
        Store a chunk in the chunk store.
        
        Args:
            chunk_hash: Hash of the chunk
            chunk_data: Chunk data
            metadata: Optional metadata
            
        Returns:
            True if stored successfully
        """
        try:
            chunk_path = self.storage_path / f"{chunk_hash}.chunk"
            
            # Store chunk data
            with open(chunk_path, 'wb') as f:
                f.write(chunk_data)
            
            # Update index
            self.chunk_index[chunk_hash] = {
                "size": len(chunk_data),
                "path": str(chunk_path),
                "metadata": metadata or {},
                "ref_count": 1
            }
            
            return True
        
        except Exception as e:
            logging.error(f"Error storing chunk {chunk_hash}: {e}")
            return False
    
    def retrieve_chunk(self, chunk_hash: str) -> Optional[bytes]:
        """
        Retrieve a chunk from the store.
        
        Args:
            chunk_hash: Hash of the chunk
            
        Returns:
            Chunk data or None if not found
        """
        try:
            if chunk_hash not in self.chunk_index:
                return None
            
            chunk_path = self.chunk_index[chunk_hash]["path"]
            with open(chunk_path, 'rb') as f:
                return f.read()
        
        except Exception as e:
            logging.error(f"Error retrieving chunk {chunk_hash}: {e}")
            return None
    
    def has_chunk(self, chunk_hash: str) -> bool:
        """Check if a chunk exists in the store."""
        return chunk_hash in self.chunk_index
    
    def delete_chunk(self, chunk_hash: str) -> bool:
        """
        Delete a chunk from the store.
        
        Args:
            chunk_hash: Hash of the chunk
            
        Returns:
            True if deleted successfully
        """
        try:
            if chunk_hash not in self.chunk_index:
                return False
            
            chunk_info = self.chunk_index[chunk_hash]
            chunk_path = chunk_info["path"]
            
            # Decrease reference count
            chunk_info["ref_count"] -= 1
            
            # Delete if no more references
            if chunk_info["ref_count"] <= 0:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
                del self.chunk_index[chunk_hash]
            
            return True
        
        except Exception as e:
            logging.error(f"Error deleting chunk {chunk_hash}: {e}")
            return False
    
    def get_store_stats(self) -> Dict[str, Any]:
        """Get chunk store statistics."""
        total_size = sum(info["size"] for info in self.chunk_index.values())
        
        return {
            "total_chunks": len(self.chunk_index),
            "total_size": total_size,
            "total_size_formatted": format_bytes(total_size),
            "storage_path": str(self.storage_path)
        }
    
    def cleanup_unreferenced(self) -> int:
        """
        Clean up chunks with zero references.
        
        Returns:
            Number of chunks cleaned up
        """
        cleanup_count = 0
        chunks_to_remove = []
        
        for chunk_hash, info in self.chunk_index.items():
            if info["ref_count"] <= 0:
                chunks_to_remove.append(chunk_hash)
        
        for chunk_hash in chunks_to_remove:
            if self.delete_chunk(chunk_hash):
                cleanup_count += 1
        
        return cleanup_count 