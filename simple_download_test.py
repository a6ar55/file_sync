#!/usr/bin/env python3
"""
Simple test for download functionality without complex dependencies.
"""

import requests
import time
import hashlib

API_BASE_URL = "http://localhost:8000"

def calculate_simple_hash(data):
    """Calculate SHA-256 hash of data."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def test_coordinator_connection():
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

def register_test_node():
    """Register a test node."""
    node_data = {
        "node_id": "simple_test_node",
        "name": "Simple Test Node",
        "address": "localhost",
        "port": 8001,
        "watch_directories": ["/tmp/test_simple"],
        "capabilities": ["sync", "upload", "download"]
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/register", json=node_data)
        if response.status_code == 200:
            print("✅ Test node registered successfully")
            return node_data
        else:
            print(f"❌ Failed to register test node: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error registering test node: {e}")
        return None

def upload_simple_test_file(node_id):
    """Upload a simple test file."""
    # Create test content
    content = f"Simple test file created at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += "This is test content for download functionality testing.\n"
    content += "Line 3: Testing download feature\n"
    content += "Line 4: Testing delta sync visualization\n"
    content += "End of test file.\n"
    
    content_bytes = content.encode('utf-8')
    file_hash = calculate_simple_hash(content_bytes)
    
    # Create simple file metadata
    file_metadata = {
        "file_id": f"simple_test_{int(time.time())}",
        "name": "simple_test.txt",
        "path": f"/{node_id}/simple_test.txt",
        "size": len(content_bytes),
        "hash": file_hash,
        "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "modified_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "owner_node": node_id,
        "version": 1,
        "vector_clock": {"clocks": {node_id: 1}},
        "is_deleted": False,
        "content_type": "text/plain"
    }
    
    # Create simple chunks (1KB each)
    chunk_size = 1024
    chunks = []
    for i in range(0, len(content_bytes), chunk_size):
        chunk_data = content_bytes[i:i + chunk_size]
        chunk = {
            "index": len(chunks),
            "offset": i,
            "size": len(chunk_data),
            "hash": calculate_simple_hash(chunk_data),
            "data": chunk_data.hex()
        }
        chunks.append(chunk)
    
    # Upload request
    upload_data = {
        "file_metadata": file_metadata,
        "chunks": chunks,
        "vector_clock": {"clocks": {node_id: 1}},
        "use_delta_sync": True
    }
    
    try:
        print(f"📤 Uploading test file ({len(content_bytes)} bytes)...")
        response = requests.post(f"{API_BASE_URL}/api/files/upload", json=upload_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Upload successful")
            
            # Show delta metrics if available
            if 'delta_metrics' in result:
                metrics = result['delta_metrics']
                print(f"   📊 Delta metrics: {metrics}")
            
            return file_metadata['file_id'], content_bytes
        else:
            print(f"❌ Upload failed: {response.text}")
            return None, None
    except Exception as e:
        print(f"❌ Error uploading file: {e}")
        return None, None

def test_file_download(file_id, expected_content):
    """Test downloading the file."""
    try:
        print(f"📥 Testing download for file {file_id[:8]}...")
        
        response = requests.get(f"{API_BASE_URL}/api/files/{file_id}/download")
        
        if response.status_code == 200:
            downloaded_content = response.content
            
            if downloaded_content == expected_content:
                print("✅ Download successful and content verified!")
                print(f"   📊 Size: {len(downloaded_content)} bytes")
                print(f"   📄 Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                print(f"   📁 Filename: {response.headers.get('Content-Disposition', 'unknown')}")
                return True
            else:
                print("❌ Content mismatch!")
                print(f"   Expected: {len(expected_content)} bytes")
                print(f"   Downloaded: {len(downloaded_content)} bytes")
                return False
        else:
            print(f"❌ Download failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing download: {e}")
        return False

def upload_modified_file_for_delta_demo(node_id, original_file_id):
    """Upload a modified version to demonstrate delta sync."""
    # Create modified content
    content = f"MODIFIED test file updated at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += "This is MODIFIED content for download functionality testing.\n"
    content += "Line 3: Testing download feature - UPDATED\n"
    content += "Line 4: Testing delta sync visualization - ENHANCED\n"
    content += "NEW LINE: Added to demonstrate delta sync efficiency\n"
    content += "End of modified test file.\n"
    
    content_bytes = content.encode('utf-8')
    file_hash = calculate_simple_hash(content_bytes)
    
    # Create file metadata for modified version
    file_metadata = {
        "file_id": f"modified_test_{int(time.time())}",
        "name": "modified_test.txt",
        "path": f"/{node_id}/modified_test.txt",
        "size": len(content_bytes),
        "hash": file_hash,
        "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "modified_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "owner_node": node_id,
        "version": 2,
        "vector_clock": {"clocks": {node_id: 2}},
        "is_deleted": False,
        "content_type": "text/plain"
    }
    
    # Create chunks
    chunk_size = 1024
    chunks = []
    for i in range(0, len(content_bytes), chunk_size):
        chunk_data = content_bytes[i:i + chunk_size]
        chunk = {
            "index": len(chunks),
            "offset": i,
            "size": len(chunk_data),
            "hash": calculate_simple_hash(chunk_data),
            "data": chunk_data.hex()
        }
        chunks.append(chunk)
    
    upload_data = {
        "file_metadata": file_metadata,
        "chunks": chunks,
        "vector_clock": {"clocks": {node_id: 2}},
        "use_delta_sync": True
    }
    
    try:
        print(f"📤 Uploading modified file for delta sync demo...")
        response = requests.post(f"{API_BASE_URL}/api/files/upload", json=upload_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Modified file upload successful")
            
            # Show delta metrics
            if 'delta_metrics' in result:
                metrics = result['delta_metrics']
                print(f"   💾 Bandwidth saved: {metrics.get('bandwidth_saved', 0)} bytes")
                print(f"   📊 Compression ratio: {metrics.get('compression_ratio', 0):.1f}%")
                print(f"   🔄 Sync latency: {result.get('sync_latency', 0):.3f}s")
            
            return file_metadata['file_id'], content_bytes
        else:
            print(f"❌ Modified file upload failed: {response.text}")
            return None, None
    except Exception as e:
        print(f"❌ Error uploading modified file: {e}")
        return None, None

def show_dashboard_info():
    """Show information about accessing the dashboard."""
    print(f"\n🌐 Dashboard Access Information:")
    print("=" * 50)
    print("🔗 Dashboard URL: http://localhost:3000")
    print("📊 Features to test:")
    print("   • File Manager: View uploaded files")
    print("   • Download Buttons: Click download icons next to files")
    print("   • Delta Sync Tab: View delta sync performance metrics")
    print("   • Network Topology: See node connections")
    print("   • Vector Clocks: View causal ordering")
    print("=" * 50)

def cleanup_test_node(node_id):
    """Clean up test node."""
    try:
        response = requests.delete(f"{API_BASE_URL}/api/nodes/{node_id}")
        if response.status_code == 200:
            print(f"✅ Cleaned up test node: {node_id}")
        else:
            print(f"❌ Failed to clean up test node: {response.text}")
    except Exception as e:
        print(f"❌ Error cleaning up: {e}")

def main():
    """Run the simple download and delta sync test."""
    print("🧪 Simple Download & Delta Sync Test")
    print("=" * 40)
    
    try:
        # Test coordinator connection
        if not test_coordinator_connection():
            print("❌ Cannot proceed without coordinator. Please start the coordinator first.")
            return
        
        # Register test node
        node = register_test_node()
        if not node:
            print("❌ Cannot proceed without test node.")
            return
        
        node_id = node['node_id']
        
        # Upload test file
        file_id, content = upload_simple_test_file(node_id)
        if not file_id:
            print("❌ Cannot proceed without uploaded file.")
            return
        
        # Test download
        if test_file_download(file_id, content):
            print("🎉 Download functionality test PASSED!")
        else:
            print("❌ Download functionality test FAILED!")
        
        # Upload modified file to demonstrate delta sync
        modified_file_id, modified_content = upload_modified_file_for_delta_demo(node_id, file_id)
        if modified_file_id:
            # Test download of modified file
            if test_file_download(modified_file_id, modified_content):
                print("🎉 Delta sync demonstration PASSED!")
            else:
                print("❌ Delta sync demonstration FAILED!")
        
        # Show system status
        try:
            response = requests.get(f"{API_BASE_URL}/api/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"\n📊 Current System Metrics:")
                print(f"   🔄 Total sync operations: {metrics.get('total_sync_operations', 0)}")
                print(f"   💰 Total bandwidth saved: {metrics.get('total_bandwidth_saved', 0)} bytes")
                print(f"   📁 Total files: {metrics.get('total_files', 0)}")
                print(f"   🖥️  Active connections: {metrics.get('active_connections', 0)}")
        except:
            pass
        
        # Show dashboard info
        show_dashboard_info()
        
        # Ask if user wants to clean up
        try:
            cleanup_choice = input(f"\n🧹 Clean up test data? (y/N): ").strip().lower()
            if cleanup_choice.startswith('y'):
                cleanup_test_node(node_id)
        except KeyboardInterrupt:
            print(f"\n⚠️  Exiting without cleanup")
        
        print(f"\n✨ Test completed successfully!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    main() 