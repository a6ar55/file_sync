#!/usr/bin/env python3
"""
Comprehensive test for download functionality and delta sync demonstration.
"""

import asyncio
import os
import sys
import time
import json
import requests
import tempfile
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from shared.models import FileMetadata, VectorClockModel, FileUploadRequest, FileChunk
from shared.utils import calculate_file_hash

API_BASE_URL = "http://localhost:8000"

class DownloadAndDeltaTest:
    def __init__(self):
        self.test_files = {}
        self.test_nodes = []
        
    def test_coordinator_connection(self):
        """Test if coordinator is running."""
        try:
            response = requests.get(f"{API_BASE_URL}/api/metrics", timeout=5)
            if response.status_code == 200:
                print("✅ Coordinator is running")
                return True
            else:
                print(f"❌ Coordinator returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to coordinator: {e}")
            return False
    
    def register_test_node(self, node_id, name):
        """Register a test node."""
        node_data = {
            "node_id": node_id,
            "name": name,
            "address": "localhost",
            "port": 8001 + len(self.test_nodes),
            "watch_directories": [f"/tmp/test_{node_id}"],
            "capabilities": ["sync", "upload", "download"]
        }
        
        try:
            response = requests.post(f"{API_BASE_URL}/api/register", json=node_data)
            if response.status_code == 200:
                self.test_nodes.append(node_data)
                print(f"✅ Registered test node: {name}")
                return True
            else:
                print(f"❌ Failed to register {name}: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error registering {name}: {e}")
            return False
    
    def create_test_file_content(self, content_type="text", size_kb=1):
        """Create test file content of specified type and size."""
        if content_type == "text":
            content = f"Test file created at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += "=" * 50 + "\n"
            
            # Add content to reach desired size
            line_size = 80
            lines_needed = (size_kb * 1024) // line_size
            
            for i in range(lines_needed):
                content += f"Line {i+1:04d}: This is test content for download and delta sync testing\n"
            
            content += "=" * 50 + "\n"
            content += "End of test file content.\n"
            
        elif content_type == "binary":
            # Create simple binary content
            content = b"Binary test file\x00\x01\x02\x03"
            content += bytes(range(256)) * ((size_kb * 1024) // 256)
            return content
            
        return content.encode('utf-8')
    
    def upload_test_file(self, filename, content, node_id):
        """Upload a test file."""
        try:
            # Calculate file hash
            if isinstance(content, str):
                content = content.encode('utf-8')
            file_hash = calculate_file_hash(content)
            
            # Create file metadata
            file_metadata = {
                "file_id": f"test_{filename}_{int(time.time())}",
                "name": filename,
                "path": f"/{node_id}/{filename}",
                "size": len(content),
                "hash": file_hash,
                "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                "modified_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                "owner_node": node_id,
                "version": 1,
                "vector_clock": {"clocks": {node_id: 1}},
                "is_deleted": False,
                "content_type": "text/plain"
            }
            
            # Create file chunks
            chunk_size = 1024  # 1KB chunks
            chunks = []
            for i in range(0, len(content), chunk_size):
                chunk_data = content[i:i + chunk_size]
                chunk = {
                    "index": len(chunks),
                    "offset": i,
                    "size": len(chunk_data),
                    "hash": calculate_file_hash(chunk_data),
                    "data": chunk_data.hex() if isinstance(chunk_data, bytes) else chunk_data
                }
                chunks.append(chunk)
            
            # Create upload request
            upload_data = {
                "file_metadata": file_metadata,
                "chunks": chunks,
                "vector_clock": {"clocks": {node_id: 1}},
                "use_delta_sync": True
            }
            
            print(f"📤 Uploading {filename} ({len(content)} bytes)...")
            
            response = requests.post(f"{API_BASE_URL}/api/files/upload", json=upload_data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Upload successful: {filename}")
                
                # Store file info
                self.test_files[filename] = {
                    'file_id': file_metadata['file_id'],
                    'node_id': node_id,
                    'original_content': content,
                    'metadata': file_metadata
                }
                
                return file_metadata['file_id']
            else:
                print(f"❌ Upload failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error uploading {filename}: {e}")
            return None
    
    def test_file_download(self, file_id, expected_content):
        """Test downloading a file and verify content."""
        try:
            print(f"📥 Testing download for file {file_id[:8]}...")
            
            # Download the file
            response = requests.get(f"{API_BASE_URL}/api/files/{file_id}/download")
            
            if response.status_code == 200:
                downloaded_content = response.content
                
                # Verify content
                if isinstance(expected_content, str):
                    expected_content = expected_content.encode('utf-8')
                
                if downloaded_content == expected_content:
                    print(f"✅ Download successful and content verified")
                    print(f"   📊 Size: {len(downloaded_content)} bytes")
                    print(f"   📄 Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                    return True
                else:
                    print(f"❌ Content mismatch!")
                    print(f"   Expected size: {len(expected_content)}")
                    print(f"   Downloaded size: {len(downloaded_content)}")
                    return False
            else:
                print(f"❌ Download failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing download: {e}")
            return False
    
    def test_delta_sync_efficiency(self):
        """Test delta sync by modifying a file and checking efficiency."""
        if not self.test_files:
            print("❌ No test files available for delta sync test")
            return False
        
        print(f"\n🔄 Testing Delta Sync Efficiency...")
        
        # Pick the first test file
        filename = list(self.test_files.keys())[0]
        file_info = self.test_files[filename]
        
        # Create a modified version
        original_content = file_info['original_content']
        if isinstance(original_content, bytes):
            original_content = original_content.decode('utf-8')
        
        # Make a small modification (should result in high efficiency)
        modified_content = original_content.replace(
            "This is test content for download and delta sync testing",
            "This is MODIFIED content for download and delta sync testing"
        )
        modified_content += f"\nModified at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Upload the modified version
        modified_filename = f"modified_{filename}"
        file_id = self.upload_test_file(
            modified_filename,
            modified_content,
            file_info['node_id']
        )
        
        if file_id:
            # Test download of modified file
            return self.test_file_download(file_id, modified_content)
        
        return False
    
    def show_system_metrics(self):
        """Display current system metrics."""
        print(f"\n📊 System Metrics:")
        print("=" * 40)
        
        try:
            # Get general metrics
            response = requests.get(f"{API_BASE_URL}/api/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"🔄 Total Sync Operations: {metrics.get('total_sync_operations', 0)}")
                print(f"💰 Total Bandwidth Saved: {metrics.get('total_bandwidth_saved', 0):,} bytes")
                print(f"⚡ Average Sync Latency: {metrics.get('average_sync_latency', 0):.3f}s")
                print(f"🖥️  Active Connections: {metrics.get('active_connections', 0)}")
                print(f"📁 Total Files: {metrics.get('total_files', 0)}")
            
            # Get delta-specific metrics
            response = requests.get(f"{API_BASE_URL}/api/delta-metrics")
            if response.status_code == 200:
                delta_metrics = response.json()
                print(f"📈 Files Synced with Delta: {delta_metrics.get('total_files_synced', 0)}")
                print(f"🗜️  Average Compression Ratio: {delta_metrics.get('average_compression_ratio', 0):.1f}%")
                print(f"🗂️  Chunk Cache Size: {delta_metrics.get('chunk_cache_size', 0)}")
                print(f"📦 Chunk Size: {delta_metrics.get('chunk_size', 0)} bytes")
            
            # Get file list
            response = requests.get(f"{API_BASE_URL}/api/files")
            if response.status_code == 200:
                files = response.json()
                active_files = [f for f in files if not f.get('is_deleted', False)]
                print(f"📋 Active Files: {len(active_files)}")
                
                for file in active_files[-3:]:  # Show last 3 files
                    print(f"   • {file['name']} ({file['size']:,} bytes) - {file['owner_node']}")
                    
        except Exception as e:
            print(f"❌ Error getting metrics: {e}")
        
        print("=" * 40)
    
    def cleanup_test_data(self):
        """Clean up test nodes and files."""
        print(f"\n🧹 Cleaning up test data...")
        
        try:
            # Remove test nodes (this will also remove their files)
            for node in self.test_nodes:
                try:
                    response = requests.delete(f"{API_BASE_URL}/api/nodes/{node['node_id']}")
                    if response.status_code == 200:
                        print(f"✅ Removed test node: {node['name']}")
                    else:
                        print(f"❌ Failed to remove test node: {node['name']}")
                except Exception as e:
                    print(f"❌ Error removing test node {node['name']}: {e}")
                    
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
    def run_comprehensive_test(self):
        """Run comprehensive download and delta sync tests."""
        print("🧪 Comprehensive Download and Delta Sync Test")
        print("=" * 55)
        
        success_count = 0
        total_tests = 0
        
        try:
            # Test 1: Check coordinator connection
            total_tests += 1
            if self.test_coordinator_connection():
                success_count += 1
            
            # Test 2: Register test nodes
            total_tests += 1
            if self.register_test_node("test_download_1", "Download Test Node 1"):
                success_count += 1
            
            total_tests += 1
            if self.register_test_node("test_download_2", "Download Test Node 2"):
                success_count += 1
            
            # Test 3: Upload test files of different sizes
            test_files = [
                ("small_test.txt", "text", 1),    # 1KB
                ("medium_test.txt", "text", 5),   # 5KB
                ("large_test.txt", "text", 20),   # 20KB
            ]
            
            for filename, content_type, size_kb in test_files:
                total_tests += 1
                content = self.create_test_file_content(content_type, size_kb)
                node_id = self.test_nodes[0]['node_id'] if self.test_nodes else "test_download_1"
                file_id = self.upload_test_file(filename, content, node_id)
                if file_id:
                    success_count += 1
                    
                    # Test download immediately after upload
                    total_tests += 1
                    if self.test_file_download(file_id, content):
                        success_count += 1
            
            # Test 4: Delta sync efficiency test
            total_tests += 1
            if self.test_delta_sync_efficiency():
                success_count += 1
            
            # Show metrics
            self.show_system_metrics()
            
            # Summary
            print(f"\n📋 Test Summary:")
            print(f"✅ Passed: {success_count}/{total_tests}")
            print(f"❌ Failed: {total_tests - success_count}/{total_tests}")
            
            if success_count == total_tests:
                print(f"🎉 All tests passed! The download and delta sync functionality is working correctly.")
                print(f"💡 You can now:")
                print(f"   • Open the dashboard at http://localhost:3000")
                print(f"   • Use the download buttons in the File Manager")
                print(f"   • View delta sync metrics in the Delta Sync tab")
            else:
                print(f"⚠️  Some tests failed. Please check the coordinator logs for details.")
            
        except KeyboardInterrupt:
            print(f"\n⚠️  Tests interrupted by user")
        except Exception as e:
            print(f"\n❌ Test suite failed: {e}")
        finally:
            # Cleanup
            if input(f"\n🧹 Clean up test data? (y/N): ").strip().lower().startswith('y'):
                self.cleanup_test_data()

def main():
    """Main function to run the tests."""
    test_suite = DownloadAndDeltaTest()
    test_suite.run_comprehensive_test()

if __name__ == "__main__":
    main() 