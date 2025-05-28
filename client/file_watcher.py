import os
import time
from datetime import datetime
from typing import Dict, Callable, Set, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from shared.utils import calculate_file_hash, get_file_info


class FileChangeHandler(FileSystemEventHandler):
    """File system event handler for watching file changes."""
    
    def __init__(self, callback: Callable[[str, str, dict], None], ignore_patterns: Set[str] = None):
        super().__init__()
        self.callback = callback
        self.ignore_patterns = ignore_patterns or {'.DS_Store', '.git', '__pycache__', '.pyc', '.tmp'}
        self.debounce_time = 1.0  # Seconds to wait before processing a change
        self.pending_changes: Dict[str, float] = {}  # file_path -> timestamp
        
    def should_ignore(self, file_path: str) -> bool:
        """Check if file should be ignored based on patterns."""
        filename = os.path.basename(file_path)
        for pattern in self.ignore_patterns:
            if pattern in filename:
                return True
        return False
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if not event.is_directory and not self.should_ignore(event.src_path):
            self._schedule_change(event.src_path, 'created')
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if not event.is_directory and not self.should_ignore(event.src_path):
            self._schedule_change(event.src_path, 'modified')
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if not event.is_directory and not self.should_ignore(event.src_path):
            self._schedule_change(event.src_path, 'deleted')
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename events."""
        if hasattr(event, 'dest_path'):
            if not event.is_directory and not self.should_ignore(event.src_path):
                self._schedule_change(event.src_path, 'deleted')
            if not event.is_directory and not self.should_ignore(event.dest_path):
                self._schedule_change(event.dest_path, 'created')
    
    def _schedule_change(self, file_path: str, event_type: str):
        """Schedule a file change for processing with debouncing."""
        current_time = time.time()
        self.pending_changes[file_path] = current_time
        
        # Process change after debounce period
        def process_after_delay():
            time.sleep(self.debounce_time)
            if (file_path in self.pending_changes and 
                self.pending_changes[file_path] == current_time):
                # No newer change has been scheduled
                del self.pending_changes[file_path]
                self._process_change(file_path, event_type)
        
        import threading
        threading.Thread(target=process_after_delay, daemon=True).start()
    
    def _process_change(self, file_path: str, event_type: str):
        """Process a file change event."""
        try:
            file_info = get_file_info(file_path)
            
            # Calculate file hash if file exists
            file_hash = ""
            if file_info['exists'] and event_type != 'deleted':
                file_hash = calculate_file_hash(file_path)
            
            change_info = {
                'event_type': event_type,
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_size': file_info['size'],
                'file_hash': file_hash,
                'modified_time': file_info['modified_time'],
                'timestamp': datetime.now()
            }
            
            # Call the callback function
            self.callback(file_path, event_type, change_info)
            
        except Exception as e:
            print(f"Error processing file change {file_path}: {e}")


class FileWatcher:
    """
    File system watcher that monitors directories for changes
    and notifies the sync engine.
    """
    
    def __init__(self, 
                 sync_directories: List[str], 
                 change_callback: Callable[[str, str, dict], None],
                 ignore_patterns: Set[str] = None):
        self.sync_directories = sync_directories
        self.change_callback = change_callback
        self.ignore_patterns = ignore_patterns or set()
        
        # Add common ignore patterns
        self.ignore_patterns.update({
            '.DS_Store', '.git', '__pycache__', '.pyc', '.tmp', 
            '.swp', '.lock', '~', '.bak'
        })
        
        self.observer = Observer()
        self.handler = FileChangeHandler(
            callback=self._on_file_change,
            ignore_patterns=self.ignore_patterns
        )
        
        self.is_watching = False
        self.file_states: Dict[str, dict] = {}  # Track file states for change detection
    
    def start_watching(self):
        """Start watching all configured directories."""
        if self.is_watching:
            return
        
        # Perform initial scan of directories
        self._initial_scan()
        
        # Start watching directories
        for directory in self.sync_directories:
            if os.path.exists(directory):
                self.observer.schedule(self.handler, directory, recursive=True)
                print(f"Started watching directory: {directory}")
            else:
                print(f"Warning: Directory does not exist: {directory}")
        
        self.observer.start()
        self.is_watching = True
        print("File watcher started")
    
    def stop_watching(self):
        """Stop watching directories."""
        if not self.is_watching:
            return
        
        self.observer.stop()
        self.observer.join()
        self.is_watching = False
        print("File watcher stopped")
    
    def _initial_scan(self):
        """Perform initial scan of directories to establish baseline."""
        print("Performing initial scan of sync directories...")
        
        for directory in self.sync_directories:
            if not os.path.exists(directory):
                continue
                
            for root, dirs, files in os.walk(directory):
                # Filter out ignored directories
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in self.ignore_patterns)]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    if self.handler.should_ignore(file_path):
                        continue
                    
                    try:
                        file_info = get_file_info(file_path)
                        if file_info['exists']:
                            file_hash = calculate_file_hash(file_path)
                            
                            self.file_states[file_path] = {
                                'size': file_info['size'],
                                'modified_time': file_info['modified_time'],
                                'hash': file_hash
                            }
                    except Exception as e:
                        print(f"Error scanning file {file_path}: {e}")
        
        print(f"Initial scan complete. Found {len(self.file_states)} files.")
    
    def _on_file_change(self, file_path: str, event_type: str, change_info: dict):
        """Handle file change events with deduplication."""
        try:
            # Check if this is a real change
            if event_type in ['created', 'modified']:
                current_state = {
                    'size': change_info['file_size'],
                    'modified_time': change_info['modified_time'],
                    'hash': change_info['file_hash']
                }
                
                # Compare with previous state
                previous_state = self.file_states.get(file_path)
                
                if previous_state and self._states_equal(previous_state, current_state):
                    # No real change detected
                    return
                
                # Update file state
                self.file_states[file_path] = current_state
                
            elif event_type == 'deleted':
                # Remove from tracked files
                self.file_states.pop(file_path, None)
            
            # Forward to sync engine
            self.change_callback(file_path, event_type, change_info)
            
        except Exception as e:
            print(f"Error handling file change {file_path}: {e}")
    
    def _states_equal(self, state1: dict, state2: dict) -> bool:
        """Compare two file states to determine if they're equal."""
        return (state1['size'] == state2['size'] and
                state1['hash'] == state2['hash'])
    
    def add_directory(self, directory: str):
        """Add a new directory to watch."""
        if directory not in self.sync_directories:
            self.sync_directories.append(directory)
            
            if self.is_watching and os.path.exists(directory):
                self.observer.schedule(self.handler, directory, recursive=True)
                print(f"Added directory to watch: {directory}")
    
    def remove_directory(self, directory: str):
        """Remove a directory from watching."""
        if directory in self.sync_directories:
            self.sync_directories.remove(directory)
            
            # Remove file states for this directory
            files_to_remove = [path for path in self.file_states.keys() 
                             if path.startswith(directory)]
            for file_path in files_to_remove:
                del self.file_states[file_path]
            
            # Note: Observer doesn't have a direct way to unwatch a specific directory
            # You would need to recreate the observer to remove watches
            print(f"Removed directory from watch: {directory}")
    
    def get_watched_files(self) -> List[str]:
        """Get list of all currently watched files."""
        return list(self.file_states.keys())
    
    def get_file_state(self, file_path: str) -> dict:
        """Get current state of a specific file."""
        return self.file_states.get(file_path, {})
    
    def force_scan(self, directory: str = None):
        """Force a scan of specified directory or all directories."""
        directories_to_scan = [directory] if directory else self.sync_directories
        
        for dir_path in directories_to_scan:
            if not os.path.exists(dir_path):
                continue
                
            print(f"Force scanning directory: {dir_path}")
            
            for root, dirs, files in os.walk(dir_path):
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in self.ignore_patterns)]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    if self.handler.should_ignore(file_path):
                        continue
                    
                    try:
                        file_info = get_file_info(file_path)
                        if file_info['exists']:
                            file_hash = calculate_file_hash(file_path)
                            
                            current_state = {
                                'size': file_info['size'],
                                'modified_time': file_info['modified_time'],
                                'hash': file_hash
                            }
                            
                            previous_state = self.file_states.get(file_path)
                            
                            if not previous_state or not self._states_equal(previous_state, current_state):
                                # File has changed or is new
                                change_type = 'created' if not previous_state else 'modified'
                                
                                change_info = {
                                    'event_type': change_type,
                                    'file_path': file_path,
                                    'file_name': os.path.basename(file_path),
                                    'file_size': file_info['size'],
                                    'file_hash': file_hash,
                                    'modified_time': file_info['modified_time'],
                                    'timestamp': datetime.now()
                                }
                                
                                self.file_states[file_path] = current_state
                                self.change_callback(file_path, change_type, change_info)
                                
                    except Exception as e:
                        print(f"Error force scanning file {file_path}: {e}")
    
    def get_stats(self) -> dict:
        """Get watcher statistics."""
        return {
            'is_watching': self.is_watching,
            'watched_directories': len(self.sync_directories),
            'tracked_files': len(self.file_states),
            'ignore_patterns': list(self.ignore_patterns)
        } 