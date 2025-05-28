# File Sync Dashboard

Real-time web dashboard for the Distributed File Synchronization System.

## Features

- **Real-time Visualization**: See file synchronization happening live between nodes
- **Node Management**: Register and manage multiple client nodes
- **File Upload**: Drag-and-drop file upload with progress tracking
- **Sync Monitoring**: Watch files replicate across the network with animated arrows
- **WebSocket Integration**: Real-time updates via WebSocket connection to coordinator
- **Modern UI**: Built with React, Tailwind CSS, and Framer Motion

## Quick Start

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

3. Open http://localhost:3000 in your browser

## System Integration

The dashboard connects to:
- **Coordinator API**: http://localhost:8000 (REST API)
- **WebSocket**: ws://localhost:8000/ws (Real-time updates)

## Usage

1. **Register Nodes**: Use the "Nodes" tab to add client nodes to the network
2. **Upload Files**: Click "Upload File" to add files to any node
3. **Watch Synchronization**: See real-time file replication with visual indicators
4. **Monitor Status**: Track node status, file counts, and sync progress

## Components

- `App.jsx` - Main application component
- `NodeCard.jsx` - Individual node display with file list
- `SyncVisualization.jsx` - Animated network visualization
- `FileUploadModal.jsx` - File upload interface
- `NodeManager.jsx` - Node registration and management
- `useWebSocket.js` - WebSocket connection hook
- `api.js` - API utilities for coordinator communication

## Technologies

- React 18 with hooks
- Tailwind CSS for styling
- Framer Motion for animations
- React Dropzone for file uploads
- React Toastify for notifications
- Axios for HTTP requests 