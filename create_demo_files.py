#!/usr/bin/env python3
"""
Demo script to showcase the distributed file sync system with delta synchronization.
This script will create test files, upload them, and demonstrate delta sync capabilities.
"""

import asyncio
import os
import sys
import time
import json
import random
import string
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from shared.models import FileMetadata, VectorClockModel, FileUploadRequest, FileChunk
from shared.utils import calculate_file_hash

API_BASE_URL = "http://localhost:8000"

class DeltaSyncDemo:
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.demo_files = {}
        self.nodes = []
        
    async def setup_demo_nodes(self):
        """Create demo nodes for testing."""
        print("🔧 Setting up demo nodes...")
        
        demo_nodes = [
            {
                "node_id": "demo_node_1",
                "name": "Demo Node 1 (Primary)",
                "address": "localhost",
                "port": 8001,
                "watch_directories": ["/tmp/demo_sync_1"],
                "capabilities": ["sync", "upload", "download"]
            },
            {
                "node_id": "demo_node_2", 
                "name": "Demo Node 2 (Secondary)",
                "address": "localhost",
                "port": 8002,
                "watch_directories": ["/tmp/demo_sync_2"],
                "capabilities": ["sync", "upload", "download"]
            },
            {
                "node_id": "demo_node_3",
                "name": "Demo Node 3 (Tertiary)", 
                "address": "localhost",
                "port": 8003,
                "watch_directories": ["/tmp/demo_sync_3"],
                "capabilities": ["sync", "upload", "download"]
            }
        ]
        
        for node_data in demo_nodes:
            try:
                response = await self.http_client.post(
                    f"{API_BASE_URL}/api/register",
                    json=node_data
                )
                if response.status_code == 200:
                    self.nodes.append(node_data)
                    print(f"✅ Registered {node_data['name']}")
                else:
                    print(f"❌ Failed to register {node_data['name']}: {response.text}")
            except Exception as e:
                print(f"❌ Error registering {node_data['name']}: {e}")
        
        await asyncio.sleep(1)  # Give time for registration to complete
    
    def create_demo_content(self, size_type="small"):
        """Create demo file content for testing delta sync."""
        if size_type == "small":
            content = "This is a small demo file for testing delta synchronization.\n"
            content += "Line 2: Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n"
            content += "Line 3: Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n"
            content += "Line 4: Ut enim ad minim veniam, quis nostrud exercitation.\n"
            content += "Line 5: Original content that will be modified in delta sync demo.\n"
            
        elif size_type == "medium":
            content = "Medium-sized file for delta sync demonstration.\n"
            content += "=" * 80 + "\n"
            for i in range(50):
                content += f"Line {i+1:02d}: Random data - {''.join(random.choices(string.ascii_letters + string.digits, k=40))}\n"
            content += "=" * 80 + "\n"
            content += "End of medium file content.\n"
            
        elif size_type == "large":
            content = "Large file for comprehensive delta sync testing.\n"
            content += "=" * 100 + "\n"
            for i in range(200):
                content += f"Section {i+1:03d}: {''.join(random.choices(string.ascii_letters + string.digits + ' ', k=80))}\n"
                if i % 20 == 0:
                    content += "-" * 100 + "\n"
            content += "=" * 100 + "\n"
            content += "End of large file content.\n"
            
        return content.encode('utf-8')
    
    def modify_content_for_delta(self, original_content, modification_type="minor"):
        """Modify content to demonstrate delta sync efficiency."""
        content = original_content.decode('utf-8')
        
        if modification_type == "minor":
            # Change just one line to show high efficiency
            content = content.replace(
                "Line 5: Original content that will be modified in delta sync demo.",
                "Line 5: MODIFIED content demonstrating efficient delta synchronization!"
            )
            content += f"\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
        elif modification_type == "medium":
            # Change several lines
            lines = content.split('\n')
            for i in range(5, min(15, len(lines))):
                if lines[i].startswith("Line"):
                    lines[i] = f"MODIFIED {lines[i]}"
            content = '\n'.join(lines)
            content += f"\n\nModification timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
        elif modification_type == "major":
            # Add new content blocks
            content += "\n" + "=" * 80 + "\n"
            content += "MAJOR MODIFICATION SECTION\n"
            content += "=" * 80 + "\n"
            for i in range(20):
                content += f"New line {i+1}: Added content for delta sync testing\n"
            content += "=" * 80 + "\n"
            
        return content.encode('utf-8')
    
    async def upload_file(self, filename, content, node_id, use_delta=True):
        """Upload a file to demonstrate sync capabilities."""
        try:
            # Calculate file hash
            file_hash = calculate_file_hash(content)
            
            # Create file metadata
            file_metadata = FileMetadata(
                file_id=f"demo_{filename}_{int(time.time())}",
                name=filename,
                path=f"/{node_id}/{filename}",
                size=len(content),
                hash=file_hash,
                created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                modified_at=time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                owner_node=node_id,
                version=1,
                vector_clock=VectorClockModel(clocks={node_id: 1}),
                is_deleted=False,
                content_type="text/plain"
            )
            
            # Create file chunks
            chunk_size = 1024  # 1KB chunks for demo
            chunks = []
            for i in range(0, len(content), chunk_size):
                chunk_data = content[i:i + chunk_size]
                chunk = FileChunk(
                    index=len(chunks),
                    offset=i,
                    size=len(chunk_data),
                    hash=calculate_file_hash(chunk_data),
                    data=chunk_data
                )
                chunks.append(chunk)
            
            # Create upload request
            upload_request = FileUploadRequest(
                file_metadata=file_metadata,
                chunks=chunks,
                vector_clock=VectorClockModel(clocks={node_id: 1}),
                use_delta_sync=use_delta
            )
            
            print(f"📤 Uploading {filename} ({len(content)} bytes) to {node_id}...")
            
            response = await self.http_client.post(
                f"{API_BASE_URL}/api/files/upload",
                json={
                    "file_metadata": file_metadata.model_dump(),
                    "chunks": [chunk.model_dump() for chunk in chunks],
                    "vector_clock": upload_request.vector_clock.model_dump(),
                    "use_delta_sync": use_delta
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Upload successful: {filename}")
                if 'delta_metrics' in result:
                    metrics = result['delta_metrics']
                    print(f"   💾 Bandwidth saved: {metrics.get('bandwidth_saved', 0)} bytes")
                    print(f"   📊 Compression ratio: {metrics.get('compression_ratio', 0):.1f}%")
                
                # Store file info for later modifications
                self.demo_files[filename] = {
                    'file_id': file_metadata.file_id,
                    'node_id': node_id,
                    'content': content,
                    'metadata': file_metadata
                }
                
                return True
            else:
                print(f"❌ Upload failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error uploading {filename}: {e}")
            return False
    
    async def demonstrate_delta_sync(self):
        """Demonstrate delta synchronization with file modifications."""
        print("\n🔄 Demonstrating Delta Synchronization...")
        
        if not self.demo_files:
            print("❌ No demo files available for delta sync demonstration")
            return
        
        # Pick a file to modify
        filename = list(self.demo_files.keys())[0]
        file_info = self.demo_files[filename]
        
        print(f"\n📝 Modifying {filename} to demonstrate delta sync...")
        
        # Create modified versions with different change levels
        modifications = [
            ("minor", "minor changes"),
            ("medium", "moderate changes"), 
            ("major", "major additions")
        ]
        
        for mod_type, description in modifications:
            print(f"\n🔧 Applying {description}...")
            
            # Modify the content
            modified_content = self.modify_content_for_delta(
                file_info['content'], 
                mod_type
            )
            
            # Upload the modified version
            modified_filename = f"{filename.split('.')[0]}_{mod_type}.txt"
            success = await self.upload_file(
                modified_filename,
                modified_content,
                file_info['node_id'],
                use_delta=True
            )
            
            if success:
                await asyncio.sleep(2)  # Give time for sync to complete
        
        print(f"\n✅ Delta sync demonstration completed!")
    
    async def show_system_status(self):
        """Display current system status and metrics."""
        print("\n📊 System Status and Metrics:")
        print("=" * 60)
        
        try:
            # Get nodes
            response = await self.http_client.get(f"{API_BASE_URL}/api/nodes")
            if response.status_code == 200:
                nodes = response.json()
                print(f"🖥️  Registered Nodes: {len(nodes)}")
                for node in nodes:
                    print(f"   • {node.get('name', node['node_id'])} ({node['status']})")
            
            # Get files
            response = await self.http_client.get(f"{API_BASE_URL}/api/files")
            if response.status_code == 200:
                files = response.json()
                active_files = [f for f in files if not f.get('is_deleted', False)]
                total_size = sum(f.get('size', 0) for f in active_files)
                print(f"📁 Active Files: {len(active_files)}")
                print(f"💾 Total Size: {total_size:,} bytes ({total_size / 1024:.1f} KB)")
            
            # Get metrics
            response = await self.http_client.get(f"{API_BASE_URL}/api/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"🔄 Sync Operations: {metrics.get('total_sync_operations', 0)}")
                print(f"💰 Bandwidth Saved: {metrics.get('total_bandwidth_saved', 0):,} bytes")
                print(f"⚡ Avg Sync Latency: {metrics.get('average_sync_latency', 0):.3f}s")
            
            # Get delta metrics
            response = await self.http_client.get(f"{API_BASE_URL}/api/delta-metrics")
            if response.status_code == 200:
                delta_metrics = response.json()
                print(f"📈 Delta Sync Efficiency: {delta_metrics.get('average_compression_ratio', 0):.1f}%")
                print(f"🗂️  Cached Chunks: {delta_metrics.get('chunk_cache_size', 0)}")
                
        except Exception as e:
            print(f"❌ Error getting system status: {e}")
        
        print("=" * 60)
    
    async def cleanup_demo_data(self):
        """Clean up demo nodes and files."""
        print("\n🧹 Cleaning up demo data...")
        
        try:
            # Remove demo nodes
            for node in self.nodes:
                try:
                    response = await self.http_client.delete(
                        f"{API_BASE_URL}/api/nodes/{node['node_id']}"
                    )
                    if response.status_code == 200:
                        print(f"✅ Removed {node['name']}")
                    else:
                        print(f"❌ Failed to remove {node['name']}")
                except Exception as e:
                    print(f"❌ Error removing {node['name']}: {e}")
                    
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
    async def run_full_demo(self):
        """Run the complete demo sequence."""
        print("🚀 Starting Distributed File Sync Demo")
        print("=" * 50)
        
        try:
            # Setup
            await self.setup_demo_nodes()
            await asyncio.sleep(2)
            
            # Create and upload initial demo files
            print("\n📁 Creating demo files...")
            
            demo_files = [
                ("small_demo.txt", "small"),
                ("medium_demo.txt", "medium"),
                ("large_demo.txt", "large")
            ]
            
            for filename, size_type in demo_files:
                content = self.create_demo_content(size_type)
                node_id = random.choice(self.nodes)['node_id']
                await self.upload_file(filename, content, node_id, use_delta=False)
                await asyncio.sleep(1)
            
            # Show initial status
            await self.show_system_status()
            
            # Demonstrate delta sync
            await self.demonstrate_delta_sync()
            
            # Show final status
            await self.show_system_status()
            
            print(f"\n🎉 Demo completed successfully!")
            print(f"💡 Open the dashboard at http://localhost:3000 to see the visual interface")
            print(f"🔍 Try downloading files using the download buttons in the file manager")
            print(f"📊 Check the Delta Sync tab for performance metrics")
            
        except KeyboardInterrupt:
            print(f"\n⚠️  Demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
        finally:
            await self.http_client.aclose()
    
    async def run_interactive_demo(self):
        """Run an interactive demo where user can choose actions."""
        print("🎮 Interactive Distributed File Sync Demo")
        print("=" * 50)
        
        try:
            await self.setup_demo_nodes()
            
            while True:
                print(f"\n📋 Available Actions:")
                print("1. Upload small test file")
                print("2. Upload medium test file") 
                print("3. Upload large test file")
                print("4. Demonstrate delta sync")
                print("5. Show system status")
                print("6. Clean up and exit")
                
                try:
                    choice = input("\nSelect an action (1-6): ").strip()
                    
                    if choice == "1":
                        content = self.create_demo_content("small")
                        node_id = random.choice(self.nodes)['node_id']
                        await self.upload_file(f"small_{int(time.time())}.txt", content, node_id)
                        
                    elif choice == "2":
                        content = self.create_demo_content("medium")
                        node_id = random.choice(self.nodes)['node_id']
                        await self.upload_file(f"medium_{int(time.time())}.txt", content, node_id)
                        
                    elif choice == "3":
                        content = self.create_demo_content("large")
                        node_id = random.choice(self.nodes)['node_id']
                        await self.upload_file(f"large_{int(time.time())}.txt", content, node_id)
                        
                    elif choice == "4":
                        await self.demonstrate_delta_sync()
                        
                    elif choice == "5":
                        await self.show_system_status()
                        
                    elif choice == "6":
                        await self.cleanup_demo_data()
                        break
                        
                    else:
                        print("❌ Invalid choice. Please select 1-6.")
                        
                except KeyboardInterrupt:
                    print(f"\n⚠️  Exiting...")
                    break
                    
        except Exception as e:
            print(f"❌ Interactive demo failed: {e}")
        finally:
            await self.http_client.aclose()

async def main():
    """Main function to run the demo."""
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        demo = DeltaSyncDemo()
        await demo.run_interactive_demo()
    else:
        demo = DeltaSyncDemo()
        await demo.run_full_demo()

if __name__ == "__main__":
    asyncio.run(main()) 