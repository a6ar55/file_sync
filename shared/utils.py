"""
Utility functions for the distributed file synchronization system.
"""

import hashlib
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union, Iterator
import json
import logging
import asyncio
import functools


def generate_file_id(file_path: str) -> str:
    """Generate a unique file ID based on path and timestamp."""
    return hashlib.sha256(f"{file_path}_{datetime.now().isoformat()}".encode()).hexdigest()[:16]


def generate_version_id() -> str:
    """Generate a unique version ID."""
    return str(uuid.uuid4())


def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        return ""
    except Exception as e:
        logging.error(f"Error calculating hash for {file_path}: {e}")
        return ""


def calculate_content_hash(content: bytes) -> str:
    """Calculate SHA-256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def get_file_chunks(file_path: str, chunk_size: int = 4096) -> List[Dict[str, Any]]:
    """Split a file into chunks and return chunk information."""
    chunks = []
    try:
        with open(file_path, "rb") as f:
            offset = 0
            index = 0
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                
                chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                chunks.append({
                    "index": index,
                    "offset": offset,
                    "size": len(chunk_data),
                    "hash": chunk_hash,
                    "data": chunk_data
                })
                
                offset += len(chunk_data)
                index += 1
                
    except Exception as e:
        logging.error(f"Error chunking file {file_path}: {e}")
        
    return chunks


def get_content_chunks(content: bytes, chunk_size: int = 4096) -> List[Dict[str, Any]]:
    """Split content into chunks and return chunk information."""
    chunks = []
    offset = 0
    index = 0
    
    while offset < len(content):
        chunk_data = content[offset:offset + chunk_size]
        chunk_hash = hashlib.sha256(chunk_data).hexdigest()
        
        chunks.append({
            "index": index,
            "offset": offset,
            "size": len(chunk_data),
            "hash": chunk_hash,
            "data": chunk_data
        })
        
        offset += len(chunk_data)
        index += 1
        
    return chunks


def rolling_hash(data: bytes, window_size: int = 64) -> int:
    """Simple rolling hash implementation."""
    if len(data) < window_size:
        return hash(data)
    
    hash_value = 0
    for byte in data[:window_size]:
        hash_value = (hash_value * 31 + byte) % (2**32)
    
    return hash_value


def find_chunk_boundaries(content: bytes, avg_chunk_size: int = 4096) -> List[int]:
    """Find optimal chunk boundaries using rolling hash."""
    if len(content) <= avg_chunk_size:
        return [len(content)]
    
    boundaries = []
    window_size = min(64, avg_chunk_size // 4)
    
    for i in range(window_size, len(content) - window_size):
        window = content[i-window_size:i]
        hash_val = rolling_hash(window, window_size)
        
        # Use rolling hash to find natural boundaries
        if hash_val % avg_chunk_size == 0:
            boundaries.append(i)
    
    # Ensure we have at least one boundary at the end
    if not boundaries or boundaries[-1] != len(content):
        boundaries.append(len(content))
    
    return boundaries


def ensure_directory(path: str) -> None:
    """Ensure a directory exists, create if it doesn't."""
    Path(path).mkdir(parents=True, exist_ok=True)


def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get comprehensive file information."""
    try:
        stat = os.stat(file_path)
        return {
            "size": stat.st_size,
            "modified_time": datetime.fromtimestamp(stat.st_mtime),
            "created_time": datetime.fromtimestamp(stat.st_ctime),
            "permissions": oct(stat.st_mode)[-3:],
            "is_file": os.path.isfile(file_path),
            "is_directory": os.path.isdir(file_path),
            "exists": True
        }
    except FileNotFoundError:
        return {"exists": False}
    except Exception as e:
        logging.error(f"Error getting file info for {file_path}: {e}")
        return {"exists": False, "error": str(e)}


def format_bytes(bytes_value: int) -> str:
    """Format bytes into human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 1:
        return f"{seconds*1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{int(minutes)}m {remaining_seconds:.1f}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{int(hours)}h {int(remaining_minutes)}m"


def is_ignored_file(file_path: str, ignore_patterns: List[str] = None) -> bool:
    """Check if a file should be ignored based on patterns."""
    if ignore_patterns is None:
        ignore_patterns = [
            '*.pyc', '*.pyo', '*.pyd', '__pycache__',
            '.git', '.svn', '.hg',
            '.DS_Store', 'Thumbs.db',
            '*.tmp', '*.temp', '*.log',
            '.env', '.venv', 'node_modules'
        ]
    
    import fnmatch
    file_name = os.path.basename(file_path)
    file_path_relative = file_path
    
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(file_path_relative, pattern):
            return True
    
    return False


def safe_json_serialize(obj: Any) -> str:
    """Safely serialize object to JSON, handling datetime and other types."""
    def default_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    try:
        return json.dumps(obj, default=default_serializer, indent=2)
    except Exception as e:
        logging.error(f"Error serializing to JSON: {e}")
        return "{}"


def safe_json_deserialize(json_str: str) -> Any:
    """Safely deserialize JSON string."""
    try:
        return json.loads(json_str)
    except Exception as e:
        logging.error(f"Error deserializing JSON: {e}")
        return {}


def generate_unique_id(prefix: str = "") -> str:
    """Generate a unique ID using timestamp and random component."""
    import time
    import random
    timestamp = int(time.time() * 1000)
    random_part = random.randint(1000, 9999)
    unique_id = f"{timestamp}{random_part}"
    
    if prefix:
        return f"{prefix}_{unique_id}"
    return unique_id


def measure_time(func):
    """Decorator to measure function execution time."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        logging.debug(f"{func.__name__} took {format_duration(duration)}")
        return result
    return wrapper


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry function on failure."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logging.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logging.error(f"All {max_retries} attempts failed for {func.__name__}")
            
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


def validate_file_path(file_path: str, base_directory: str = None) -> bool:
    """Validate that a file path is safe and within allowed directory."""
    try:
        # Resolve the path to handle .. and . components
        resolved_path = os.path.realpath(file_path)
        
        # Check if path exists and is within base directory if specified
        if base_directory:
            base_real = os.path.realpath(base_directory)
            if not resolved_path.startswith(base_real):
                return False
        
        # Check for suspicious patterns
        suspicious_patterns = ['..', '~', '$']
        for pattern in suspicious_patterns:
            if pattern in file_path:
                return False
        
        return True
    except Exception:
        return False


class ConfigManager:
    """Simple configuration manager."""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
        
        # Return default configuration
        return {
            "coordinator": {
                "host": "localhost",
                "port": 8000,
                "database_url": "sqlite:///coordinator.db"
            },
            "client": {
                "chunk_size": 4096,
                "max_retries": 3,
                "sync_interval": 30,
                "ignore_patterns": [
                    "*.pyc", "*.pyo", "__pycache__",
                    ".git", ".svn", ".DS_Store",
                    "*.tmp", "*.log"
                ]
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
    
    def save_config(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'coordinator.host')."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation."""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value 


def calculate_file_hash_from_data(data: bytes) -> str:
    """Calculate SHA-256 hash from file data bytes."""
    sha256_hash = hashlib.sha256()
    sha256_hash.update(data)
    return sha256_hash.hexdigest() 