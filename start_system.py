#!/usr/bin/env python3
"""
Startup script for the complete File Sync System.
Runs both coordinator and React dashboard.
"""

import subprocess
import sys
import os
import time
import signal
import threading
from pathlib import Path

def print_banner():
    """Print startup banner."""
    print("=" * 60)
    print("🚀 DISTRIBUTED FILE SYNCHRONIZATION SYSTEM")
    print("=" * 60)
    print("📡 Starting coordinator server...")
    print("🌐 Starting React dashboard...")
    print("=" * 60)

def run_coordinator():
    """Run the coordinator server."""
    try:
        print("📡 Coordinator: Starting on http://localhost:8000")
        coordinator_process = subprocess.Popen([
            sys.executable, "run_coordinator.py"
        ], cwd=os.getcwd())
        return coordinator_process
    except Exception as e:
        print(f"❌ Failed to start coordinator: {e}")
        return None

def run_dashboard():
    """Run the React dashboard."""
    try:
        dashboard_dir = Path("dashboard")
        if not dashboard_dir.exists():
            print("❌ Dashboard directory not found!")
            return None
            
        print("🌐 Dashboard: Starting on http://localhost:3000")
        dashboard_process = subprocess.Popen([
            "npm", "start"
        ], cwd=dashboard_dir)
        return dashboard_process
    except Exception as e:
        print(f"❌ Failed to start dashboard: {e}")
        return None

def wait_for_coordinator():
    """Wait for coordinator to be ready."""
    import requests
    import time
    
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:8000/api/metrics", timeout=2)
            if response.status_code == 200:
                print("✅ Coordinator is ready!")
                return True
        except:
            pass
        
        print(f"⏳ Waiting for coordinator... ({i+1}/{max_retries})")
        time.sleep(2)
    
    print("❌ Coordinator failed to start!")
    return False

def main():
    """Main startup function."""
    print_banner()
    
    # Global process references
    coordinator_proc = None
    dashboard_proc = None
    
    def cleanup():
        """Cleanup function to stop all processes."""
        print("\n🛑 Shutting down system...")
        
        if coordinator_proc:
            print("📡 Stopping coordinator...")
            coordinator_proc.terminate()
            coordinator_proc.wait()
        
        if dashboard_proc:
            print("🌐 Stopping dashboard...")
            dashboard_proc.terminate()
            dashboard_proc.wait()
        
        print("👋 System stopped successfully!")
    
    def signal_handler(signum, frame):
        """Handle system signals for graceful shutdown."""
        cleanup()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start coordinator
        coordinator_proc = run_coordinator()
        if not coordinator_proc:
            print("❌ Failed to start coordinator server!")
            sys.exit(1)
        
        # Wait for coordinator to be ready
        if not wait_for_coordinator():
            cleanup()
            sys.exit(1)
        
        # Start dashboard
        dashboard_proc = run_dashboard()
        if not dashboard_proc:
            print("❌ Failed to start dashboard!")
            cleanup()
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("🎉 SYSTEM READY!")
        print("=" * 60)
        print("📡 Coordinator API: http://localhost:8000")
        print("📊 API Documentation: http://localhost:8000/docs")
        print("🌐 Web Dashboard: http://localhost:3000")
        print("🔌 WebSocket: ws://localhost:8000/ws")
        print("=" * 60)
        print("📝 INSTRUCTIONS:")
        print("1. Open http://localhost:3000 in your browser")
        print("2. Register nodes using the 'Nodes' tab")
        print("3. Upload files using the 'Upload File' button")
        print("4. Watch real-time synchronization!")
        print("=" * 60)
        print("Press Ctrl+C to stop the system")
        print("=" * 60)
        
        # Wait for processes
        while True:
            # Check if processes are still running
            if coordinator_proc.poll() is not None:
                print("❌ Coordinator process died!")
                break
                
            if dashboard_proc.poll() is not None:
                print("❌ Dashboard process died!")
                break
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main() 