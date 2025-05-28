#!/usr/bin/env python3
"""
Test script to verify sync progress visualization in the dashboard.
This script uploads a file and monitors the sync events to ensure
the progress bars and animations work correctly.
"""

import requests
import time
import json

def test_sync_progress():
    """Test sync progress visualization."""
    print("🚀 Testing Sync Progress Visualization for Dashboard")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    timestamp = int(time.time())
    
    # Register test nodes with proper IDs
    node1_id = f"ui_test_node_1_{timestamp}"
    node2_id = f"ui_test_node_2_{timestamp}"
    
    print(f"📝 Registering {node1_id}...")
    node1_data = {
        "node_id": node1_id,
        "name": "UI Test Node 1",
        "address": "localhost",
        "port": 8300,
        "watch_directories": ["/tmp/ui_test1"],
        "capabilities": ["sync", "upload"]
    }
    
    response = requests.post(f"{base_url}/api/register", json=node1_data)
    if response.status_code == 200:
        print("✅ UI Test Node 1 registered")
    else:
        print(f"❌ Failed to register node 1: {response.text}")
        return
    
    print(f"📝 Registering {node2_id}...")
    node2_data = {
        "node_id": node2_id,
        "name": "UI Test Node 2",
        "address": "localhost", 
        "port": 8301,
        "watch_directories": ["/tmp/ui_test2"],
        "capabilities": ["sync", "upload"]
    }
    
    response = requests.post(f"{base_url}/api/register", json=node2_data)
    if response.status_code == 200:
        print("✅ UI Test Node 2 registered")
    else:
        print(f"❌ Failed to register node 2: {response.text}")
        return
    
    # Wait a moment for registration to complete
    time.sleep(1)
    
    # Upload a test file from node 1
    file_id = f"ui_test_file_{timestamp}"
    test_content = f"Test file content for UI sync progress visualization at {time.ctime()}"
    
    print("\n📤 Uploading test file to trigger sync events...")
    upload_data = {
        "file_metadata": {
            "file_id": file_id,
            "name": "ui_test_sync.txt",
            "path": f"/{node1_id}/ui_test_sync.txt",
            "size": len(test_content),
            "hash": "",  # Will be calculated
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "modified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "owner_node": node1_id,
            "version": 1,
            "vector_clock": {"clocks": {node1_id: 1}},
            "is_deleted": False,
            "content_type": "text/plain"
        },
        "chunks": [{
            "index": 0,
            "offset": 0,
            "size": len(test_content),
            "hash": "",
            "data": test_content.encode().hex()
        }],
        "vector_clock": {"clocks": {node1_id: 1}},
        "use_delta_sync": False
    }
    
    response = requests.post(f"{base_url}/api/files/upload", json=upload_data)
    if response.status_code == 200:
        print("✅ File upload initiated!")
        result = response.json()
        print(f"   Version ID: {result.get('version_id')}")
        print(f"   Sync Latency: {result.get('sync_latency', 0):.3f}s")
    else:
        print(f"❌ Upload failed: {response.text}")
        return
    
    # Monitor sync events for a few seconds
    print("\n📊 Monitoring sync events...")
    for i in range(15):
        time.sleep(0.5)
        
        # Get recent events
        response = requests.get(f"{base_url}/api/events?limit=20")
        if response.status_code == 200:
            events = response.json()
            
            # Filter for sync-related events
            sync_events = [e for e in events if 'sync' in e.get('event_type', '')]
            
            if sync_events:
                print(f"   📈 Found {len(sync_events)} sync events:")
                for j, event in enumerate(sync_events[:5]):
                    data = event.get('data', {})
                    event_type = event.get('event_type')
                    action = data.get('action', 'N/A')
                    progress = data.get('progress', 'N/A')
                    file_name = data.get('file_name', 'N/A')
                    
                    print(f"      {j+1}. {event_type} - {action} - {file_name} - {progress}%")
                break
        else:
            print(f"   ⚠️  Failed to get events: {response.status_code}")
    
    # Final verification
    print("\n🔍 Final Verification:")
    
    # Check files on both nodes
    for node_id, node_name in [(node1_id, "UI Test Node 1"), (node2_id, "UI Test Node 2")]:
        response = requests.get(f"{base_url}/api/nodes/{node_id}/files")
        if response.status_code == 200:
            files = response.json()
            matching_files = [f for f in files if 'ui_test_sync' in f.get('name', '')]
            print(f"   📂 {node_name}: {len(matching_files)} matching files")
        else:
            print(f"   ❌ Failed to get files for {node_name}")
    
    # Get final events count
    response = requests.get(f"{base_url}/api/events?limit=50")
    if response.status_code == 200:
        events = response.json()
        sync_events = [e for e in events if 'sync' in e.get('event_type', '')]
        progress_events = [e for e in sync_events if e.get('event_type') == 'file_sync_progress']
        completed_events = [e for e in sync_events if e.get('event_type') == 'sync_completed']
        
        print(f"\n📊 Event Summary:")
        print(f"   Total sync events: {len(sync_events)}")
        print(f"   Progress events: {len(progress_events)}")
        print(f"   Completed events: {len(completed_events)}")
        
        if progress_events:
            print(f"\n📈 Progress Event Details:")
            for event in progress_events[:3]:
                data = event.get('data', {})
                print(f"   - {data.get('action', 'N/A')}: {data.get('progress', 'N/A')}% - {data.get('file_name', 'N/A')}")
    
    print("\n🧹 Cleanup...")
    
    # Remove test nodes
    for node_id, node_name in [(node1_id, "UI Test Node 1"), (node2_id, "UI Test Node 2")]:
        response = requests.delete(f"{base_url}/api/nodes/{node_id}")
        if response.status_code == 200:
            print(f"   ✅ Removed {node_name}")
        else:
            print(f"   ❌ Failed to remove {node_name}")
    
    print("\n" + "=" * 60)
    print("🎉 UI SYNC PROGRESS TEST COMPLETED!")
    print("   Check the dashboard at http://localhost:3000 to see the sync visualization")
    print("   The events should now show up in the Network Synchronization component")


if __name__ == "__main__":
    test_sync_progress() 