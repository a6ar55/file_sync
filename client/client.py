import asyncio
import signal
import sys
import os
from typing import List, Set
from datetime import datetime

from client.file_watcher import FileWatcher
from client.sync_engine import SyncEngine


class DistributedFileClient:
    """
    Main client application for distributed file synchronization.
    Integrates file watching and synchronization capabilities.
    """
    
    def __init__(self, 
                 node_id: str,
                 node_name: str,
                 sync_directories: List[str],
                 coordinator_url: str = "http://localhost:8000",
                 ignore_patterns: Set[str] = None):
        self.node_id = node_id
        self.node_name = node_name
        self.sync_directories = sync_directories
        self.coordinator_url = coordinator_url
        
        # Initialize components
        self.sync_engine = SyncEngine(
            node_id=node_id,
            node_name=node_name,
            coordinator_url=coordinator_url
        )
        
        self.file_watcher = FileWatcher(
            sync_directories=sync_directories,
            change_callback=self._on_file_change,
            ignore_patterns=ignore_patterns
        )
        
        # Application state
        self.is_running = False
        self.startup_complete = False
        
        # Setup event callbacks
        self.sync_engine.on_file_synced = self._on_file_synced
        self.sync_engine.on_conflict_detected = self._on_conflict_detected
        self.sync_engine.on_sync_progress = self._on_sync_progress
        
        # Performance tracking
        self.session_stats = {
            'session_start': datetime.now(),
            'files_processed': 0,
            'sync_operations': 0,
            'errors': 0
        }
    
    async def start(self) -> bool:
        """Start the distributed file client."""
        try:
            print(f"Starting Distributed File Client: {self.node_name} ({self.node_id})")
            print(f"Coordinator URL: {self.coordinator_url}")
            print(f"Sync Directories: {self.sync_directories}")
            
            # Initialize sync engine
            print("Initializing sync engine...")
            if not await self.sync_engine.initialize():
                print("Failed to initialize sync engine")
                return False
            
            # Start file watcher
            print("Starting file watcher...")
            self.file_watcher.start_watching()
            
            # Perform initial sync of existing files
            print("Performing initial synchronization...")
            await self._initial_sync()
            
            self.is_running = True
            self.startup_complete = True
            
            print("✅ Distributed File Client started successfully!")
            print("Press Ctrl+C to stop the client")
            
            # Setup signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            return True
            
        except Exception as e:
            print(f"Error starting client: {e}")
            return False
    
    async def _initial_sync(self):
        """Perform initial synchronization of existing files."""
        print("Scanning directories for existing files...")
        
        initial_files = []
        for directory in self.sync_directories:
            if not os.path.exists(directory):
                print(f"Warning: Directory does not exist: {directory}")
                continue
            
            for root, dirs, files in os.walk(directory):
                # Filter out ignored directories
                dirs[:] = [d for d in dirs if not self.file_watcher.handler.should_ignore(os.path.join(root, d))]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    if not self.file_watcher.handler.should_ignore(file_path):
                        initial_files.append(file_path)
        
        print(f"Found {len(initial_files)} files for initial sync")
        
        # Sync files in batches to avoid overwhelming the coordinator
        batch_size = 5
        for i in range(0, len(initial_files), batch_size):
            batch = initial_files[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self.sync_engine.sync_file(file_path, "created") for file_path in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and failures
            successes = sum(1 for result in results if result is True)
            failures = len(results) - successes
            
            print(f"Batch {i//batch_size + 1}: {successes} successful, {failures} failed")
            
            # Brief pause between batches
            await asyncio.sleep(0.5)
        
        print("Initial synchronization completed")
    
    def _on_file_change(self, file_path: str, event_type: str, change_info: dict):
        """Handle file change events from the file watcher."""
        try:
            if not self.startup_complete:
                # Ignore changes during startup
                return
            
            print(f"File {event_type}: {file_path}")
            
            # Queue sync operation
            asyncio.create_task(self._sync_file_async(file_path, event_type, change_info))
            
            self.session_stats['files_processed'] += 1
            
        except Exception as e:
            print(f"Error handling file change {file_path}: {e}")
            self.session_stats['errors'] += 1
    
    async def _sync_file_async(self, file_path: str, event_type: str, change_info: dict):
        """Asynchronously sync a file change."""
        try:
            success = await self.sync_engine.sync_file(file_path, event_type)
            
            if success:
                self.session_stats['sync_operations'] += 1
                print(f"✅ Synced: {os.path.basename(file_path)}")
            else:
                print(f"❌ Failed to sync: {os.path.basename(file_path)}")
                self.session_stats['errors'] += 1
                
        except Exception as e:
            print(f"Error syncing file {file_path}: {e}")
            self.session_stats['errors'] += 1
    
    def _on_file_synced(self, file_path: str, version_id: str):
        """Handle successful file synchronization."""
        print(f"📄 File synced successfully: {os.path.basename(file_path)} (v{version_id[:8]})")
    
    def _on_conflict_detected(self, file_id: str, conflict_info: dict):
        """Handle conflict detection."""
        print(f"⚠️  Conflict detected for file ID: {file_id}")
        print(f"   Conflicting nodes: {conflict_info.get('conflicting_nodes', [])}")
        print("   Manual resolution may be required")
    
    def _on_sync_progress(self, file_path: str, progress: float):
        """Handle sync progress updates."""
        if progress >= 100.0:
            print(f"📤 Upload complete: {os.path.basename(file_path)}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}, shutting down...")
        asyncio.create_task(self.stop())
    
    async def stop(self):
        """Stop the distributed file client."""
        if not self.is_running:
            return
        
        print("Shutting down Distributed File Client...")
        
        try:
            # Stop file watcher
            print("Stopping file watcher...")
            self.file_watcher.stop_watching()
            
            # Shutdown sync engine
            print("Shutting down sync engine...")
            await self.sync_engine.shutdown()
            
            self.is_running = False
            print("✅ Client shutdown complete")
            
            # Print session statistics
            self._print_session_stats()
            
        except Exception as e:
            print(f"Error during shutdown: {e}")
    
    def _print_session_stats(self):
        """Print session statistics."""
        duration = datetime.now() - self.session_stats['session_start']
        
        print("\n" + "="*50)
        print("SESSION STATISTICS")
        print("="*50)
        print(f"Node ID: {self.node_id}")
        print(f"Session Duration: {duration}")
        print(f"Files Processed: {self.session_stats['files_processed']}")
        print(f"Sync Operations: {self.session_stats['sync_operations']}")
        print(f"Errors: {self.session_stats['errors']}")
        
        # Get sync engine stats
        sync_stats = self.sync_engine.get_sync_stats()
        print(f"Files Synced: {sync_stats['files_synced']}")
        print(f"Bytes Transferred: {sync_stats['bytes_transferred']:,}")
        print(f"Bytes Saved (Delta): {sync_stats['bytes_saved']:,}")
        print(f"Conflicts Detected: {sync_stats['conflicts_detected']}")
        print("="*50)
    
    async def run_interactive_mode(self):
        """Run client in interactive mode with commands."""
        if not self.is_running:
            print("Client is not running")
            return
        
        print("\nInteractive Mode - Available Commands:")
        print("  stats     - Show current statistics")
        print("  files     - List tracked files")
        print("  sync      - Force sync of all directories")
        print("  history   - Show file history (requires file ID)")
        print("  restore   - Restore file version (requires file ID and version ID)")
        print("  quit      - Exit interactive mode")
        print()
        
        while self.is_running:
            try:
                command = input("client> ").strip().lower()
                
                if command == "quit":
                    break
                elif command == "stats":
                    await self._show_stats()
                elif command == "files":
                    await self._list_files()
                elif command == "sync":
                    await self._force_sync()
                elif command.startswith("history"):
                    parts = command.split()
                    if len(parts) > 1:
                        await self._show_file_history(parts[1])
                    else:
                        print("Usage: history <file_id>")
                elif command.startswith("restore"):
                    parts = command.split()
                    if len(parts) > 2:
                        await self._restore_file_version(parts[1], parts[2])
                    else:
                        print("Usage: restore <file_id> <version_id>")
                elif command == "":
                    continue
                else:
                    print(f"Unknown command: {command}")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                print(f"Error in interactive mode: {e}")
    
    async def _show_stats(self):
        """Show current statistics."""
        sync_stats = self.sync_engine.get_sync_stats()
        watcher_stats = self.file_watcher.get_stats()
        
        print("\nCURRENT STATISTICS")
        print("-" * 30)
        print(f"Node ID: {sync_stats['node_id']}")
        print(f"Connected: {'Yes' if sync_stats['is_connected'] else 'No'}")
        print(f"Local Files: {sync_stats['local_files']}")
        print(f"Watched Directories: {watcher_stats['watched_directories']}")
        print(f"Tracked Files: {watcher_stats['tracked_files']}")
        print(f"Files Synced: {sync_stats['files_synced']}")
        print(f"Bytes Transferred: {sync_stats['bytes_transferred']:,}")
        print(f"Bytes Saved: {sync_stats['bytes_saved']:,}")
        print(f"Sync Operations: {sync_stats['sync_operations']}")
        print(f"Conflicts: {sync_stats['conflicts_detected']}")
    
    async def _list_files(self):
        """List tracked files."""
        sync_stats = self.sync_engine.get_sync_stats()
        
        print(f"\nTRACKED FILES ({sync_stats['local_files']} total)")
        print("-" * 50)
        
        for file_id, metadata in self.sync_engine.local_files.items():
            print(f"ID: {file_id[:16]}... | {metadata.name} | {metadata.size:,} bytes")
    
    async def _force_sync(self):
        """Force synchronization of all directories."""
        print("Forcing synchronization of all directories...")
        
        for directory in self.sync_directories:
            print(f"Scanning: {directory}")
            self.file_watcher.force_scan(directory)
        
        print("Force sync initiated")
    
    async def _show_file_history(self, file_id: str):
        """Show file history."""
        history = await self.sync_engine.get_file_history(file_id)
        
        if not history:
            print(f"No history found for file ID: {file_id}")
            return
        
        print(f"\nFILE HISTORY for {file_id}")
        print("-" * 50)
        
        for version in history:
            timestamp = version.get('timestamp', 'Unknown')
            version_num = version.get('version_number', 'Unknown')
            author = version.get('author', 'Unknown')
            description = version.get('description', 'No description')
            
            print(f"Version {version_num}: {timestamp}")
            print(f"  Author: {author}")
            print(f"  Description: {description}")
            print()
    
    async def _restore_file_version(self, file_id: str, version_id: str):
        """Restore a file to a specific version."""
        print(f"Restoring file {file_id} to version {version_id}...")
        
        success = await self.sync_engine.restore_file_version(file_id, version_id)
        
        if success:
            print("✅ File restored successfully")
        else:
            print("❌ Failed to restore file")
    
    async def run_until_stopped(self):
        """Run the client until it's stopped."""
        try:
            while self.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.stop()

    async def download_file(self, file_id: str, target_path: str) -> bool:
        """Download a file from the coordinator."""
        try:
            print(f"Downloading file {file_id} to {target_path}")
            
            # Get file metadata from coordinator
            response = await self.http_client.get(f"{self.coordinator_url}/api/files/{file_id}")
            if response.status_code != 200:
                print(f"Failed to get file metadata: {response.text}")
                return False
                
            metadata = response.json()
            
            # Download file content
            download_response = await self.http_client.get(
                f"{self.coordinator_url}/api/files/{file_id}/download",
                params={"node_id": self.node_id}
            )
            
            if download_response.status_code != 200:
                print(f"Failed to download file: {download_response.text}")
                return False
            
            # Ensure target directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # Write file content
            with open(target_path, 'wb') as f:
                f.write(download_response.content)
            
            print(f"✅ File downloaded successfully: {os.path.basename(target_path)}")
            return True
            
        except Exception as e:
            print(f"Error downloading file: {e}")
            return False


async def create_and_run_client(node_id: str, 
                               node_name: str,
                               sync_directories: List[str],
                               coordinator_url: str = "http://localhost:8000",
                               interactive: bool = False):
    """Create and run a distributed file client."""
    client = DistributedFileClient(
        node_id=node_id,
        node_name=node_name,
        sync_directories=sync_directories,
        coordinator_url=coordinator_url
    )
    
    # Start the client
    if await client.start():
        try:
            if interactive:
                # Run in interactive mode
                await client.run_interactive_mode()
            else:
                # Run until stopped
                await client.run_until_stopped()
        finally:
            await client.stop()
    else:
        print("Failed to start client")
        sys.exit(1)


def main():
    """Main entry point for the client application."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Distributed File Sync Client")
    parser.add_argument("--node-id", required=True, help="Unique node identifier")
    parser.add_argument("--node-name", required=True, help="Human-readable node name")
    parser.add_argument("--sync-dirs", required=True, nargs="+", help="Directories to synchronize")
    parser.add_argument("--coordinator", default="http://localhost:8000", help="Coordinator URL")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    # Validate sync directories
    for directory in args.sync_dirs:
        if not os.path.exists(directory):
            print(f"Creating directory: {directory}")
            os.makedirs(directory, exist_ok=True)
    
    # Run the client
    try:
        asyncio.run(create_and_run_client(
            node_id=args.node_id,
            node_name=args.node_name,
            sync_directories=args.sync_dirs,
            coordinator_url=args.coordinator,
            interactive=args.interactive
        ))
    except KeyboardInterrupt:
        print("\nClient stopped by user")
    except Exception as e:
        print(f"Error running client: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 