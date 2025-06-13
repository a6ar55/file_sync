import os
import hashlib
from typing import Optional, Dict, Any
import aiofiles
import asyncio
from datetime import datetime

def generate_file_id(file_path: str) -> str:
    """Generate a unique file ID based on the file path."""
    # Use a combination of path and timestamp to ensure uniqueness
    timestamp = datetime.now().timestamp()
    return hashlib.sha256(f"{file_path}:{timestamp}".encode()).hexdigest()

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        # Read the file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()

def calculate_file_hash_from_data(data: bytes) -> str:
    """Calculate SHA-256 hash from file data."""
    return hashlib.sha256(data).hexdigest()

async def safe_file_read(file_path: str) -> Optional[bytes]:
    """Safely read a file asynchronously."""
    try:
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

async def safe_file_write(file_path: str, data: bytes) -> bool:
    """Safely write data to a file asynchronously."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(data)
        return True
    except Exception as e:
        print(f"Error writing file {file_path}: {e}")
        return False

def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get file information including size and modification time."""
    try:
        stat = os.stat(file_path)
        return {
            'exists': True,
            'size': stat.st_size,
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat()
        }
    except FileNotFoundError:
        return {
            'exists': False,
            'size': 0,
            'modified_time': None,
            'created_time': None
        }
    except Exception as e:
        print(f"Error getting file info for {file_path}: {e}")
        return {
            'exists': False,
            'size': 0,
            'modified_time': None,
            'created_time': None
        }

def ensure_directory(directory: str) -> bool:
    """Ensure a directory exists, create if it doesn't."""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error creating directory {directory}: {e}")
        return False

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}" 