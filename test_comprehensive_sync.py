#!/usr/bin/env python3
"""
Comprehensive test to verify file synchronization across all nodes.
This test will register multiple nodes, upload a file, and verify it appears on all nodes.
"""

import requests
import json
import time
import asyncio
import aiohttp
from datetime import datetime

API_BASE_URL = "http://localhost:8000"

def test_sync_sync():
    """Synchronous version using requests"""
    print("🚀 Starting Comprehensive File Sync Test (Synchronous)")
    print("=" * 60)
    
    # Clean slate - register 3 test nodes
    test_nodes = []
    for i in range(3):
        node_data = {
            "node_id": f"test_sync_node_{i+1}_{int(time.time())}",
            "name": f"Test Sync Node {i+1}",
            "address": "localhost",
            "port": 8100 + i,
            "watch_directories": [f"/tmp/node_{i+1}"],
            "capabilities": ["sync", "upload", "download"]
        }
        
        print(f"📝 Registering {node_data['name']}...")
        response = requests.post(f"{API_BASE_URL}/api/register", json=node_data)
        if response.status_code == 200:
            test_nodes.append(node_data)
            print(f"✅ {node_data['name']} registered successfully")
        else:
            print(f"❌ Failed to register {node_data['name']}: {response.text}")
            return False
    
    if len(test_nodes) < 3:
        print("❌ Failed to register all test nodes")
        return False
    
    print(f"\n📊 Successfully registered {len(test_nodes)} nodes")
    
    # Wait a moment for registration to complete
    time.sleep(1)
    
    # Verify all nodes are registered
    response = requests.get(f"{API_BASE_URL}/api/nodes")
    if response.status_code == 200:
        all_nodes = response.json()
        test_node_ids = [node['node_id'] for node in test_nodes]
        registered_test_nodes = [node for node in all_nodes if node['node_id'] in test_node_ids]
        print(f"📋 Confirmed {len(registered_test_nodes)} test nodes in system")
    
    # Create and upload a test file from Node 1
    source_node = test_nodes[0]
    test_content = f"Test file content from {source_node['name']} at {datetime.now()}"
    test_content_bytes = test_content.encode('utf-8')
    
    file_metadata = {
        "file_id": f"comprehensive_test_{int(time.time())}",
        "name": "comprehensive_test_file.txt",
        "path": f"/{source_node['node_id']}/comprehensive_test_file.txt",
        "size": len(test_content_bytes),
        "hash": "",
        "created_at": datetime.now().isoformat(),
        "modified_at": datetime.now().isoformat(),
        "owner_node": source_node['node_id'],
        "version": 1,
        "vector_clock": {"clocks": {}},
        "is_deleted": False,
        "content_type": "text/plain"
    }
    
    upload_data = {
        "file_metadata": file_metadata,
        "chunks": [{
            "index": 0,
            "offset": 0,
            "size": len(test_content_bytes),
            "hash": "",
            "data": test_content
        }],
        "vector_clock": {"clocks": {source_node['node_id']: 1}},
        "use_delta_sync": True
    }
    
    print(f"\n📤 Uploading test file from {source_node['name']}...")
    print(f"   File: {file_metadata['name']}")
    print(f"   Size: {file_metadata['size']} bytes")
    print(f"   Content: {test_content[:50]}...")
    
    response = requests.post(f"{API_BASE_URL}/api/files/upload", json=upload_data)
    if response.status_code == 200:
        upload_result = response.json()
        print(f"✅ File uploaded successfully!")
        print(f"   Version ID: {upload_result.get('version_id')}")
        print(f"   Sync Latency: {upload_result.get('sync_latency', 0):.3f}s")
    else:
        print(f"❌ File upload failed: {response.status_code} - {response.text}")
        return False
    
    # Wait for synchronization to complete
    print(f"\n⏳ Waiting for synchronization to complete...")
    time.sleep(6)  # Give enough time for sync events
    
    # Check if file appears on ALL nodes
    print(f"\n🔍 Checking file synchronization across all nodes...")
    sync_success = True
    
    for i, node in enumerate(test_nodes):
        print(f"\n📂 Checking files on {node['name']} ({node['node_id']})...")
        
        # Get all files for this node
        response = requests.get(f"{API_BASE_URL}/api/nodes/{node['node_id']}/files")
        if response.status_code == 200:
            node_files = response.json()
            print(f"   📋 Total files on node: {len(node_files)}")
            
            # Look for our test file (original or replica)
            matching_files = []
            for file in node_files:
                if (file['name'] == file_metadata['name'] or 
                    file_metadata['name'] in file.get('name', '') or
                    file_metadata['file_id'] in file.get('file_id', '')):
                    matching_files.append(file)
            
            if matching_files:
                print(f"   ✅ Test file found on {node['name']}!")
                for file in matching_files:
                    print(f"      - File ID: {file['file_id']}")
                    print(f"      - Name: {file['name']}")
                    print(f"      - Path: {file['path']}")
                    print(f"      - Size: {file['size']} bytes")
                    print(f"      - Owner: {file['owner_node']}")
            else:
                print(f"   ❌ Test file NOT found on {node['name']}")
                print(f"      Available files:")
                for file in node_files:
                    print(f"        - {file['name']} (ID: {file['file_id']}, Owner: {file['owner_node']})")
                sync_success = False
        else:
            print(f"   ❌ Failed to get files for {node['name']}: {response.status_code}")
            sync_success = False
    
    # Check recent sync events
    print(f"\n📊 Checking recent sync events...")
    response = requests.get(f"{API_BASE_URL}/api/events?limit=20")
    if response.status_code == 200:
        events = response.json()
        sync_events = [e for e in events if 'sync' in e.get('event_type', '').lower()]
        print(f"   📈 Found {len(sync_events)} sync-related events")
        
        for event in sync_events[-5:]:  # Show last 5 sync events
            print(f"      - {event['event_type']}: {event.get('data', {}).get('action', 'N/A')} "
                  f"(Node: {event['node_id']}, File: {event.get('data', {}).get('file_name', 'N/A')})")
    
    # Get system metrics
    print(f"\n📊 System Metrics:")
    response = requests.get(f"{API_BASE_URL}/api/metrics")
    if response.status_code == 200:
        metrics = response.json()
        print(f"   - Total nodes: {metrics.get('registered_nodes', 0)}")
        print(f"   - Total files: {metrics.get('total_files', 0)}")
        print(f"   - Sync operations: {metrics.get('total_sync_operations', 0)}")
        print(f"   - Average latency: {metrics.get('average_sync_latency', 0):.3f}s")
    
    # Cleanup: Remove test nodes
    print(f"\n🧹 Cleaning up test nodes...")
    for node in test_nodes:
        response = requests.delete(f"{API_BASE_URL}/api/nodes/{node['node_id']}")
        if response.status_code == 200:
            print(f"   ✅ Removed {node['name']}")
        else:
            print(f"   ⚠️  Failed to remove {node['name']}: {response.status_code}")
    
    # Final result
    print(f"\n" + "=" * 60)
    if sync_success:
        print("🎉 COMPREHENSIVE SYNC TEST PASSED!")
        print("✅ File successfully synchronized to all nodes")
    else:
        print("❌ COMPREHENSIVE SYNC TEST FAILED!")
        print("❌ File was NOT synchronized to all nodes")
    
    return sync_success

if __name__ == "__main__":
    success = test_sync_sync()
    exit(0 if success else 1) 