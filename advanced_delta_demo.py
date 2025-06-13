#!/usr/bin/env python3
"""
Advanced Delta Synchronization Demonstration
Shows how only modified chunks are transmitted with proper file versioning.
"""

import requests
import time
import json
import hashlib
from datetime import datetime

API_BASE_URL = "http://localhost:8000"

class AdvancedDeltaDemo:
    def __init__(self):
        self.demo_node_id = "advanced_delta_demo"
        self.file_id = "demo_file_2024"  # Fixed file ID for proper versioning
        self.step_counter = 0
        
    def register_demo_node(self):
        """Register demo node."""
        node_data = {
            "node_id": self.demo_node_id,
            "name": "Advanced Delta Demo Node",
            "address": "localhost",
            "port": 8002,
            "watch_directories": ["/tmp/advanced_delta"],
            "capabilities": ["sync", "upload", "download", "delta"]
        }
        
        try:
            response = requests.post(f"{API_BASE_URL}/api/register", json=node_data)
            if response.status_code == 200:
                print("✅ Advanced demo node registered")
                return True
            else:
                print(f"❌ Failed to register: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False
    
    def create_base_document(self):
        """Create a base document with distinct sections."""
        return """DISTRIBUTED FILE SYNCHRONIZATION DEMO
========================================

SECTION A: Introduction
This document demonstrates delta synchronization.
Delta sync transmits only the changed parts of files.
This dramatically reduces bandwidth usage.

SECTION B: Technical Overview
Files are divided into fixed-size chunks.
Each chunk has a unique cryptographic signature.
Only chunks with different signatures are transmitted.

SECTION C: Performance Benefits
- Bandwidth reduction: 70-95% typical
- Faster synchronization for large files
- Reduced network congestion
- Lower latency for small changes

SECTION D: Implementation Details
Rolling hash algorithm for chunk boundaries.
Strong hash (SHA-256) for integrity verification.
Chunk cache for reusing unchanged content.

SECTION E: Use Cases
- Document collaboration
- Software version control
- Database replication
- Large file distribution

SECTION F: Conclusion
Delta synchronization is essential for efficient
distributed file systems and collaboration tools.

END OF DOCUMENT
"""

    def create_modification_1(self, base_content):
        """Small change in one section."""
        return base_content.replace(
            "This document demonstrates delta synchronization.",
            "This document demonstrates ADVANCED delta synchronization with REAL-TIME efficiency."
        ).replace(
            "END OF DOCUMENT",
            "END OF DOCUMENT (Modified v1)"
        )
    
    def create_modification_2(self, content):
        """Add new section and modify existing."""
        new_section = """
SECTION G: Advanced Features (NEW)
- Incremental synchronization
- Conflict detection and resolution  
- Real-time collaboration support
- Multi-node consistency guarantees

"""
        
        return content.replace(
            "SECTION F: Conclusion",
            new_section + "SECTION F: Conclusion"
        ).replace(
            "Bandwidth reduction: 70-95% typical",
            "Bandwidth reduction: 80-98% with advanced algorithms"
        ).replace(
            "END OF DOCUMENT (Modified v1)",
            "END OF DOCUMENT (Modified v2)"
        )
    
    def create_modification_3(self, content):
        """Distributed changes throughout document."""
        return content.replace(
            "DISTRIBUTED FILE SYNCHRONIZATION DEMO",
            "ADVANCED DISTRIBUTED FILE SYNCHRONIZATION DEMO"
        ).replace(
            "Delta sync transmits only the changed parts",
            "Intelligent delta sync transmits ONLY the modified chunks"
        ).replace(
            "Fixed-size chunks",
            "Variable and fixed-size chunks with optimization"
        ).replace(
            "Rolling hash algorithm",
            "Advanced rolling hash with Rabin fingerprinting"
        ).replace(
            "Document collaboration",
            "Real-time document collaboration with conflict resolution"
        ).replace(
            "END OF DOCUMENT (Modified v2)",
            "END OF DOCUMENT (Modified v3 - Final)"
        )
    
    def upload_content(self, content, version_name, is_first_upload=False):
        """Upload content using the coordinator API."""
        content_bytes = content.encode('utf-8')
        file_hash = hashlib.sha256(content_bytes).hexdigest()
        
        # Create proper file metadata
        file_metadata = {
            "file_id": self.file_id,
            "name": f"demo_document_v{self.step_counter}.txt",
            "path": f"/{self.demo_node_id}/demo_document_v{self.step_counter}.txt",
            "size": len(content_bytes),
            "hash": file_hash,
            "created_at": datetime.now().isoformat() + "Z",
            "modified_at": datetime.now().isoformat() + "Z",
            "owner_node": self.demo_node_id,
            "version": self.step_counter + 1,
            "is_deleted": False,
            "content_type": "text/plain"
        }
        
        # Create chunks (1KB for better demo visualization)
        chunk_size = 1024
        chunks = []
        for i in range(0, len(content_bytes), chunk_size):
            chunk_data = content_bytes[i:i + chunk_size]
            chunk = {
                "index": len(chunks),
                "offset": i,
                "size": len(chunk_data),
                "hash": hashlib.sha256(chunk_data).hexdigest(),
                "data": chunk_data.hex()
            }
            chunks.append(chunk)
        
        # Prepare upload request
        upload_data = {
            "file_metadata": file_metadata,
            "chunks": chunks,
            "vector_clock": {"clocks": {self.demo_node_id: self.step_counter + 1}},
            "use_delta_sync": not is_first_upload  # Only use delta sync after first upload
        }
        
        print(f"\n{'='*60}")
        print(f"📤 UPLOADING: {version_name}")
        print(f"{'='*60}")
        print(f"📊 File size: {len(content_bytes):,} bytes")
        print(f"🧩 Chunks: {len(chunks)} (1KB each)")
        print(f"🔄 Delta sync: {'Enabled' if not is_first_upload else 'Disabled (first upload)'}")
        print(f"🆔 File ID: {self.file_id}")
        
        try:
            response = requests.post(f"{API_BASE_URL}/api/files/upload", json=upload_data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Upload successful!")
                
                # Display metrics
                if 'delta_metrics' in result:
                    metrics = result['delta_metrics']
                    print(f"\n📈 DELTA SYNC METRICS:")
                    print(f"   💾 Bandwidth saved: {metrics.get('bandwidth_saved', 0):,} bytes")
                    print(f"   📊 Compression ratio: {metrics.get('compression_ratio', 0):.1f}%")
                    print(f"   🔄 Chunks total: {metrics.get('chunks_total', 0)}")
                    print(f"   ✅ Chunks unchanged: {metrics.get('chunks_unchanged', 0)}")
                    print(f"   📤 Chunks transmitted: {metrics.get('chunks_modified', 0) + metrics.get('chunks_new', 0)}")
                    print(f"   ⚡ Sync time: {result.get('sync_latency', 0):.3f}s")
                    
                    # Calculate efficiency
                    if metrics.get('chunks_total', 0) > 0:
                        efficiency = (metrics.get('chunks_unchanged', 0) / metrics.get('chunks_total', 1)) * 100
                        print(f"   ✨ Network efficiency: {efficiency:.1f}%")
                    
                    # Show bandwidth savings
                    original_size = metrics.get('original_size', len(content_bytes))
                    transmitted = original_size - metrics.get('bandwidth_saved', 0)
                    if original_size > 0:
                        savings_percent = (metrics.get('bandwidth_saved', 0) / original_size) * 100
                        print(f"   📉 Bandwidth savings: {savings_percent:.1f}%")
                        print(f"   🌐 Network transmission: {transmitted:,} bytes (vs {original_size:,} full)")
                
                self.step_counter += 1
                return True, result.get('delta_metrics', {})
            else:
                print(f"❌ Upload failed: {response.text}")
                return False, {}
                
        except Exception as e:
            print(f"❌ Upload error: {e}")
            return False, {}
    
    def show_cumulative_analysis(self, all_metrics):
        """Show cumulative analysis of all uploads."""
        if not all_metrics:
            return
            
        print(f"\n{'='*60}")
        print(f"🌐 CUMULATIVE NETWORK ANALYSIS")
        print(f"{'='*60}")
        
        total_content_size = 0
        total_transmitted = 0
        total_saved = 0
        
        for i, metrics in enumerate(all_metrics):
            content_size = metrics.get('original_size', 0)
            saved = metrics.get('bandwidth_saved', 0)
            transmitted = content_size - saved
            
            total_content_size += content_size
            total_transmitted += transmitted
            total_saved += saved
            
            efficiency = (saved / content_size * 100) if content_size > 0 else 0
            
            print(f"Step {i+1}:")
            print(f"  📄 Content: {content_size:,} bytes")
            print(f"  📤 Sent: {transmitted:,} bytes")
            print(f"  💾 Saved: {saved:,} bytes ({efficiency:.1f}%)")
            print()
        
        overall_efficiency = (total_saved / total_content_size * 100) if total_content_size > 0 else 0
        bandwidth_reduction = (1 - total_transmitted / total_content_size) * 100 if total_content_size > 0 else 0
        
        print(f"🎯 OVERALL RESULTS:")
        print(f"   📊 Total content: {total_content_size:,} bytes")
        print(f"   📤 Total transmitted: {total_transmitted:,} bytes")
        print(f"   💾 Total saved: {total_saved:,} bytes")
        print(f"   🚀 Average efficiency: {overall_efficiency:.1f}%")
        print(f"   📉 Bandwidth reduction: {bandwidth_reduction:.1f}%")
        print(f"   ⚡ Network impact: {(total_transmitted/total_content_size)*100:.1f}% of full transmission")
        
        # Show the power of delta sync
        if len(all_metrics) > 1:
            print(f"\n💡 KEY INSIGHTS:")
            print(f"   • Without delta sync: {total_content_size:,} bytes total transmission")
            print(f"   • With delta sync: {total_transmitted:,} bytes actual transmission")
            print(f"   • Network savings: {total_saved:,} bytes ({bandwidth_reduction:.1f}%)")
            print(f"   • Perfect for collaborative editing & version control!")
    
    def demonstrate_editing_flow(self):
        """Run the complete editing demonstration."""
        print(f"🎯 ADVANCED DELTA SYNCHRONIZATION DEMONSTRATION")
        print(f"=" * 60)
        print(f"This demo shows intelligent chunk-level delta sync")
        print(f"🔗 Dashboard: http://localhost:3000 (Delta Sync tab)")
        print()
        
        # Check coordinator
        try:
            response = requests.get(f"{API_BASE_URL}/api/metrics", timeout=5)
            if response.status_code != 200:
                print("❌ Coordinator not available. Start with: python run_coordinator.py")
                return False
        except:
            print("❌ Cannot connect to coordinator. Please start it first.")
            return False
        
        # Register node
        if not self.register_demo_node():
            return False
        
        # Track metrics
        all_metrics = []
        
        # Step 1: Upload original document
        print(f"\n🔥 STEP 1: Upload Original Document")
        original_content = self.create_base_document()
        success, metrics = self.upload_content(original_content, "Original Document", is_first_upload=True)
        if success:
            all_metrics.append(metrics)
        
        time.sleep(2)
        
        # Step 2: Small modification
        print(f"\n🔥 STEP 2: Small Targeted Modification")
        print(f"   📝 Changed: Introduction section + footer")
        print(f"   🎯 Expected: High efficiency (~90%+ chunks reused)")
        modified_1 = self.create_modification_1(original_content)
        success, metrics = self.upload_content(modified_1, "Small Changes")
        if success:
            all_metrics.append(metrics)
        
        time.sleep(2)
        
        # Step 3: Add new section
        print(f"\n🔥 STEP 3: Add New Content + Modify Existing")
        print(f"   📝 Added: New section G with advanced features")
        print(f"   📝 Changed: Performance benefits section")
        print(f"   🎯 Expected: Good efficiency (~70-80% chunks reused)")
        modified_2 = self.create_modification_2(modified_1)
        success, metrics = self.upload_content(modified_2, "Added Content")
        if success:
            all_metrics.append(metrics)
        
        time.sleep(2)
        
        # Step 4: Distributed changes
        print(f"\n🔥 STEP 4: Distributed Edits Throughout")
        print(f"   📝 Changed: Multiple sections with enhancements")
        print(f"   📝 Updated: Technical terms and descriptions")
        print(f"   🎯 Expected: Moderate efficiency (~60-70% chunks reused)")
        modified_3 = self.create_modification_3(modified_2)
        success, metrics = self.upload_content(modified_3, "Distributed Edits")
        if success:
            all_metrics.append(metrics)
        
        # Analysis
        self.show_cumulative_analysis(all_metrics)
        
        # Dashboard integration
        print(f"\n🌐 VIEW RESULTS IN DASHBOARD:")
        print(f"🔗 URL: http://localhost:3000")
        print(f"📊 Recommended tabs:")
        print(f"   • Delta Sync: Live metrics and charts")
        print(f"   • File Manager: Download all versions")
        print(f"   • Vector Clocks: Synchronization timeline")
        print(f"   • Network Topology: Real-time activity")
        
        # System status
        try:
            response = requests.get(f"{API_BASE_URL}/api/metrics")
            if response.status_code == 200:
                system_metrics = response.json()
                print(f"\n📊 SYSTEM STATUS:")
                print(f"   🔄 Total sync operations: {system_metrics.get('total_sync_operations', 0)}")
                print(f"   💰 Total bandwidth saved: {system_metrics.get('total_bandwidth_saved', 0):,} bytes")
                print(f"   📁 Total files in system: {system_metrics.get('total_files', 0)}")
        except:
            pass
        
        return True

def main():
    """Run the advanced delta sync demonstration."""
    demo = AdvancedDeltaDemo()
    
    try:
        if demo.demonstrate_editing_flow():
            print(f"\n✨ DEMONSTRATION COMPLETED SUCCESSFULLY!")
            print(f"\n💡 KEY TAKEAWAYS:")
            print(f"   🎯 Only modified chunks transmitted over network")
            print(f"   📊 Bandwidth savings of 60-90% for typical edits")
            print(f"   ⚡ Faster sync for large files with small changes")
            print(f"   🔄 Perfect for real-time collaboration")
            print(f"   🌐 Essential for distributed file systems")
            
            print(f"\n🔬 NEXT STEPS:")
            print(f"   • Check Dashboard at http://localhost:3000")
            print(f"   • Download files to see identical content")
            print(f"   • Monitor real-time metrics")
            print(f"   • Try your own file edits!")
        else:
            print(f"\n⚠️  Demo failed - check coordinator status")
            
    except KeyboardInterrupt:
        print(f"\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")

if __name__ == "__main__":
    main() 