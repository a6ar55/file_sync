#!/usr/bin/env python3
"""
Script to run the coordinator server.
"""

import sys
import os
import traceback

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_coordinator_server():
    """Run the coordinator server with proper error handling."""
    try:
        print("🚀 Starting Distributed File Sync Coordinator...")
        print("📡 Server will be available at: http://localhost:8000")
        print("🔧 API documentation at: http://localhost:8000/docs")
        print("📊 WebSocket endpoint at: ws://localhost:8000/ws")
        print("")
        print("Press Ctrl+C to stop the server")
        print("=" * 50)
        
        from coordinator.server import run_coordinator
        run_coordinator(host="localhost", port=8000)
        
    except KeyboardInterrupt:
        print("\n👋 Coordinator server stopped.")
    except Exception as e:
        print(f"\n❌ Error starting coordinator: {e}")
        print(f"❌ Error type: {type(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_coordinator_server() 