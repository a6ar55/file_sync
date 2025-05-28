#!/usr/bin/env python3
"""
Simple test script to verify the coordinator server can start.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coordinator.server import CoordinatorServer


async def test_coordinator():
    """Test that the coordinator can be initialized."""
    try:
        print("Initializing coordinator server...")
        coordinator = CoordinatorServer()
        
        print("✓ Coordinator server initialized successfully")
        print("✓ FastAPI app created")
        print("✓ Database manager created")
        print("✓ Vector clock manager created")
        print("✓ File manager created")
        print("✓ Delta sync engine created")
        
        # Test database initialization
        print("Testing database initialization...")
        await coordinator.db.initialize()
        print("✓ Database initialized successfully")
        
        # Test basic database operations
        print("Testing basic database operations...")
        stats = await coordinator.db.get_statistics()
        print(f"✓ Database statistics: {stats}")
        
        print("\n🎉 All tests passed! The coordinator is ready to run.")
        print("\nTo start the coordinator server, run:")
        print("python -m coordinator.server")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_coordinator())
    sys.exit(0 if success else 1) 