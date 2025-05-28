#!/usr/bin/env python3
"""
Demo script to set up nodes for testing sync visualization in the dashboard.
Run this script, then go to the dashboard to upload files and see sync progress.
"""

import requests
import time
import sys

def main():
    timestamp = int(time.time())
    
    # Register demo nodes
    nodes = []
    for i in range(3):
        node_id = f'demo_sync_node_{i+1}_{timestamp}'
        node_data = {
            'node_id': node_id,
            'name': f'Demo Sync Node {i+1}',
            'address': 'localhost',
            'port': 8400 + i,
            'watch_directories': [f'/tmp/demo_{i+1}'],
            'capabilities': ['sync', 'upload']
        }
        
        response = requests.post('http://localhost:8000/api/register', json=node_data)
        if response.status_code == 200:
            nodes.append(node_id)
            print(f'✅ Registered {node_data["name"]}')
        else:
            print(f'❌ Failed to register {node_data["name"]}')
    
    if not nodes:
        print('No nodes registered successfully!')
        return
    
    print(f'\n🎉 {len(nodes)} demo nodes registered!')
    print('🌐 Open the dashboard: http://localhost:3000')
    print('📤 Upload files in the dashboard to see sync progress visualization')
    print('🔄 The sync progress bars and animations should now work properly')
    print('\n⚠️  Press Ctrl+C when you\'re done testing to clean up...')
    
    try:
        while True:
            time.sleep(5)
            # Keep nodes alive
            for node_id in nodes:
                try:
                    requests.get(f'http://localhost:8000/api/nodes/{node_id}')
                except:
                    pass
    except KeyboardInterrupt:
        print('\n\n🧹 Cleaning up demo nodes...')
        for node_id in nodes:
            try:
                response = requests.delete(f'http://localhost:8000/api/nodes/{node_id}')
                if response.status_code == 200:
                    print(f'✅ Removed {node_id}')
                else:
                    print(f'⚠️  Failed to remove {node_id}')
            except Exception as e:
                print(f'❌ Error removing {node_id}: {e}')
        
        print('🎯 Demo completed!')

if __name__ == '__main__':
    main() 