#!/usr/bin/env python3
"""
Working Delta Sync Demonstration
Shows the key concepts of delta synchronization with visual output.
"""

import hashlib
import time
from datetime import datetime

def calculate_chunk_hash(data):
    """Calculate SHA-256 hash of chunk data."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()[:16]  # Shortened for display

def create_chunks(content, chunk_size=512):
    """Split content into chunks with hashes."""
    chunks = []
    content_bytes = content.encode('utf-8') if isinstance(content, str) else content
    
    for i in range(0, len(content_bytes), chunk_size):
        chunk_data = content_bytes[i:i + chunk_size]
        chunk = {
            'index': len(chunks),
            'offset': i,
            'size': len(chunk_data),
            'data': chunk_data,
            'hash': calculate_chunk_hash(chunk_data),
            'text_preview': chunk_data.decode('utf-8', errors='ignore')[:50] + '...'
        }
        chunks.append(chunk)
    
    return chunks

def compare_chunks(old_chunks, new_chunks):
    """Compare chunk sets and return delta analysis."""
    old_hashes = {chunk['hash']: chunk for chunk in old_chunks}
    
    unchanged_chunks = []
    modified_chunks = []
    new_chunks_list = []
    
    for new_chunk in new_chunks:
        if new_chunk['hash'] in old_hashes:
            unchanged_chunks.append(new_chunk)
        else:
            # Check if this is a modification of an existing chunk by position
            old_chunk_at_position = None
            for old_chunk in old_chunks:
                if old_chunk['index'] == new_chunk['index']:
                    old_chunk_at_position = old_chunk
                    break
            
            if old_chunk_at_position:
                modified_chunks.append({
                    'old': old_chunk_at_position,
                    'new': new_chunk
                })
            else:
                new_chunks_list.append(new_chunk)
    
    return {
        'unchanged': unchanged_chunks,
        'modified': modified_chunks,
        'new': new_chunks_list
    }

def calculate_bandwidth_savings(old_chunks, new_chunks, delta_analysis):
    """Calculate bandwidth savings from delta sync."""
    total_old_size = sum(chunk['size'] for chunk in old_chunks)
    total_new_size = sum(chunk['size'] for chunk in new_chunks)
    
    # Only need to transmit modified and new chunks
    transmitted_size = 0
    transmitted_size += sum(mod['new']['size'] for mod in delta_analysis['modified'])
    transmitted_size += sum(chunk['size'] for chunk in delta_analysis['new'])
    
    reused_size = sum(chunk['size'] for chunk in delta_analysis['unchanged'])
    bandwidth_saved = reused_size
    
    efficiency = (bandwidth_saved / total_new_size * 100) if total_new_size > 0 else 0
    
    return {
        'total_new_size': total_new_size,
        'transmitted_size': transmitted_size,
        'bandwidth_saved': bandwidth_saved,
        'efficiency': efficiency,
        'reused_chunks': len(delta_analysis['unchanged']),
        'transmitted_chunks': len(delta_analysis['modified']) + len(delta_analysis['new'])
    }

def print_chunk_analysis(chunks, title):
    """Print visual chunk analysis."""
    print(f"\n📊 {title}")
    print("=" * 60)
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i}: [{chunk['hash']}] {chunk['size']} bytes")
        print(f"   Preview: {chunk['text_preview']}")
    print(f"Total: {len(chunks)} chunks, {sum(c['size'] for c in chunks)} bytes")

def print_delta_analysis(delta_analysis, bandwidth_stats):
    """Print delta synchronization analysis."""
    print(f"\n🔍 DELTA SYNCHRONIZATION ANALYSIS")
    print("=" * 60)
    
    print(f"✅ UNCHANGED CHUNKS (reused from cache):")
    for chunk in delta_analysis['unchanged']:
        print(f"   • Chunk {chunk['index']}: [{chunk['hash']}] {chunk['size']} bytes - REUSED")
    
    print(f"\n⚡ MODIFIED CHUNKS (must transmit):")
    for mod in delta_analysis['modified']:
        old_chunk = mod['old']
        new_chunk = mod['new']
        print(f"   • Chunk {new_chunk['index']}: [{old_chunk['hash']}] → [{new_chunk['hash']}] - CHANGED")
    
    print(f"\n➕ NEW CHUNKS (must transmit):")
    for chunk in delta_analysis['new']:
        print(f"   • Chunk {chunk['index']}: [{chunk['hash']}] {chunk['size']} bytes - NEW")
    
    print(f"\n📈 BANDWIDTH EFFICIENCY:")
    print(f"   📄 Total content: {bandwidth_stats['total_new_size']} bytes")
    print(f"   📤 Must transmit: {bandwidth_stats['transmitted_size']} bytes")
    print(f"   💾 Can reuse: {bandwidth_stats['bandwidth_saved']} bytes")
    print(f"   ✨ Efficiency: {bandwidth_stats['efficiency']:.1f}%")
    print(f"   🔄 Reused chunks: {bandwidth_stats['reused_chunks']}")
    print(f"   📤 Transmitted chunks: {bandwidth_stats['transmitted_chunks']}")

def demonstrate_delta_sync():
    """Run the delta synchronization demonstration."""
    print("🎯 DELTA SYNCHRONIZATION DEMONSTRATION")
    print("=" * 60)
    print("This demo shows how delta sync transmits only changed chunks")
    print()
    
    # Original document
    original_content = """# Project Documentation

## Introduction
This document describes our distributed file synchronization system.
The system uses advanced delta synchronization algorithms.

## Features
- Real-time synchronization
- Conflict resolution
- Vector clock ordering
- Bandwidth optimization

## Architecture
The system consists of multiple nodes that communicate via a coordinator.
Each node maintains a local file cache for efficiency.

## Performance
Delta sync reduces bandwidth usage by 70-90% for typical edits.
This makes it perfect for collaborative document editing."""

    # First modification - small changes
    modified_content_1 = original_content.replace(
        "This document describes our distributed file synchronization system.",
        "This document describes our ADVANCED distributed file synchronization system with REAL-TIME capabilities."
    ).replace(
        "Delta sync reduces bandwidth usage by 70-90% for typical edits.",
        "Our optimized delta sync reduces bandwidth usage by 80-95% for typical edits."
    )

    # Second modification - add new section
    modified_content_2 = modified_content_1 + """

## Security
- End-to-end encryption
- Authentication and authorization
- Secure key exchange protocols
- Data integrity verification

## Future Enhancements
- Machine learning optimization
- Predictive caching
- Advanced compression algorithms"""

    # Third modification - distributed changes
    modified_content_3 = modified_content_2.replace(
        "Real-time synchronization",
        "Lightning-fast real-time synchronization"
    ).replace(
        "Conflict resolution",
        "Intelligent conflict resolution with user guidance"
    ).replace(
        "The system consists of multiple nodes",
        "Our scalable system consists of multiple high-performance nodes"
    ).replace(
        "End-to-end encryption",
        "Military-grade end-to-end encryption"
    )

    # Demonstrate step by step
    documents = [
        ("Original Document", original_content),
        ("Small Changes", modified_content_1),
        ("Added New Section", modified_content_2),
        ("Distributed Updates", modified_content_3)
    ]
    
    all_bandwidth_stats = []
    previous_chunks = None
    
    for i, (title, content) in enumerate(documents):
        print(f"\n{'🔥' if i > 0 else '📄'} STEP {i+1}: {title}")
        print("=" * 60)
        
        # Create chunks for current content
        current_chunks = create_chunks(content, chunk_size=256)  # Smaller chunks for better demo
        
        # Print chunk analysis
        print_chunk_analysis(current_chunks, f"{title} - Chunk Breakdown")
        
        if previous_chunks is not None:
            # Perform delta analysis
            delta_analysis = compare_chunks(previous_chunks, current_chunks)
            bandwidth_stats = calculate_bandwidth_savings(previous_chunks, current_chunks, delta_analysis)
            
            # Print delta analysis
            print_delta_analysis(delta_analysis, bandwidth_stats)
            all_bandwidth_stats.append(bandwidth_stats)
            
            # Show what would be transmitted over network
            print(f"\n🌐 NETWORK TRANSMISSION:")
            print(f"   Without delta sync: {bandwidth_stats['total_new_size']} bytes (full file)")
            print(f"   With delta sync: {bandwidth_stats['transmitted_size']} bytes ({bandwidth_stats['efficiency']:.1f}% saved)")
            
        else:
            print(f"\n🌐 NETWORK TRANSMISSION:")
            print(f"   Initial upload: {sum(c['size'] for c in current_chunks)} bytes (full file)")
        
        previous_chunks = current_chunks
        time.sleep(1)  # Pause for effect
    
    # Summary analysis
    if all_bandwidth_stats:
        print(f"\n🎯 OVERALL DELTA SYNC PERFORMANCE")
        print("=" * 60)
        
        total_content = sum(stats['total_new_size'] for stats in all_bandwidth_stats)
        total_transmitted = sum(stats['transmitted_size'] for stats in all_bandwidth_stats)
        total_saved = sum(stats['bandwidth_saved'] for stats in all_bandwidth_stats)
        
        overall_efficiency = (total_saved / total_content * 100) if total_content > 0 else 0
        
        print(f"📊 Across {len(all_bandwidth_stats)} modifications:")
        print(f"   💾 Total content processed: {total_content:,} bytes")
        print(f"   📤 Actually transmitted: {total_transmitted:,} bytes")
        print(f"   🚀 Bandwidth saved: {total_saved:,} bytes")
        print(f"   ✨ Overall efficiency: {overall_efficiency:.1f}%")
        print(f"   📉 Network reduction: {(1 - total_transmitted/total_content)*100:.1f}%")
        
        print(f"\n💡 KEY BENEFITS:")
        print(f"   🎯 Only changed chunks transmitted")
        print(f"   💰 {overall_efficiency:.0f}% bandwidth savings")
        print(f"   ⚡ Faster sync for large files")
        print(f"   🌐 Scales efficiently with file size")
        print(f"   📝 Perfect for document collaboration")
    
    print(f"\n✨ DEMONSTRATION COMPLETE!")
    print(f"🔗 Now check the Dashboard at http://localhost:3000")
    print(f"   • File Editor tab: Edit files and see real delta sync")
    print(f"   • Delta Sync tab: Live metrics and visualizations") 

if __name__ == "__main__":
    demonstrate_delta_sync() 