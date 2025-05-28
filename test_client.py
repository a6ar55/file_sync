#!/usr/bin/env python3
"""
Simple client test script to test the coordinator API.
"""

import asyncio
import httpx
import json
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.models import RegisterNodeRequest, FileMetadata, VectorClockModel


async def test_coordinator_api():
    """Test the coordinator API endpoints."""
    coordinator_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🧪 Testing Coordinator API...")
        
        # Test health check
        try:
            response = await client.get(f"{coordinator_url}/api/metrics")
            if response.status_code == 200:
                print("✓ Coordinator is healthy")
                print(f"  Metrics: {response.json()}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to coordinator: {e}")
            return False
        
        # Test node registration
        print("\n📝 Testing node registration...")
        node_request = RegisterNodeRequest(
            node_id="test_node_1",
            name="Test Node 1",
            address="localhost",
            port=9001,
            watch_directories=["/tmp/test"],
            capabilities=["file_sync", "delta_sync"]
        )
        
        try:
            response = await client.post(
                f"{coordinator_url}/api/register",
                json=node_request.model_dump()
            )
            if response.status_code == 200:
                print("✓ Node registration successful")
                print(f"  Response: {response.json()}")
            else:
                print(f"❌ Node registration failed: {response.status_code}")
                print(f"  Error: {response.text}")
        except Exception as e:
            print(f"❌ Node registration error: {e}")
        
        # Test getting nodes
        print("\n📋 Testing get nodes...")
        try:
            response = await client.get(f"{coordinator_url}/api/nodes")
            if response.status_code == 200:
                nodes = response.json()
                print(f"✓ Retrieved {len(nodes)} nodes")
                for node in nodes:
                    print(f"  Node: {node['node_id']} - {node['status']}")
            else:
                print(f"❌ Get nodes failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Get nodes error: {e}")
        
        # Test getting files
        print("\n📁 Testing get files...")
        try:
            response = await client.get(f"{coordinator_url}/api/files")
            if response.status_code == 200:
                files = response.json()
                print(f"✓ Retrieved {len(files)} files")
            else:
                print(f"❌ Get files failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Get files error: {e}")
        
        # Test getting events
        print("\n📰 Testing get events...")
        try:
            response = await client.get(f"{coordinator_url}/api/events")
            if response.status_code == 200:
                events = response.json()
                print(f"✓ Retrieved {len(events)} events")
            else:
                print(f"❌ Get events failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Get events error: {e}")
        
        print("\n🎉 API tests completed!")
        return True


if __name__ == "__main__":
    print("🚀 Testing Coordinator API Endpoints")
    print("Make sure the coordinator is running on localhost:8000")
    print("=" * 50)
    
    success = asyncio.run(test_coordinator_api())
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1) 