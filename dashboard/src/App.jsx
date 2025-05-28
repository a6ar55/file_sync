import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { 
  Upload, 
  RefreshCw, 
  Wifi, 
  WifiOff,
  Activity,
  FileText,
  Users
} from 'lucide-react';

import NodeCard from './components/NodeCard';
import SyncVisualization from './components/SyncVisualization';
import FileUploadModal from './components/FileUploadModal';
import NodeManager from './components/NodeManager';
import useWebSocket from './hooks/useWebSocket';
import { nodeApi, fileApi, metricsApi, eventsApi } from './utils/api';
import FileManager from './components/FileManager';

function App() {
  // State management
  const [nodes, setNodes] = useState([]);
  const [files, setFiles] = useState([]);
  const [syncEvents, setSyncEvents] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [syncingFiles, setSyncingFiles] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  // WebSocket connection
  const { isConnected, lastMessage, connectionError } = useWebSocket('ws://localhost:8000/ws');

  // Load initial data
  useEffect(() => {
    loadInitialData();
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      handleWebSocketMessage(lastMessage);
    }
  }, [lastMessage]);

  const loadInitialData = async () => {
    setIsLoading(true);
    try {
      const [nodesData, filesData, eventsData, metricsData] = await Promise.all([
        nodeApi.getAll().catch(() => []),
        fileApi.getAll().catch(() => []),
        eventsApi.getRecent().catch(() => []),
        metricsApi.get().catch(() => {})
      ]);

      setNodes(nodesData);
      setFiles(filesData);
      setSyncEvents(eventsData);
      setMetrics(metricsData);
    } catch (error) {
      console.error('Error loading initial data:', error);
      toast.error('Failed to load initial data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleWebSocketMessage = (message) => {
    console.log('WebSocket message:', message);
    
    switch (message.type) {
      case 'event':
        const event = message.data;
        setSyncEvents(prev => [event, ...prev.slice(0, 49)]); // Keep last 50 events
        
        // Handle different event types
        if (event.event_type === 'file_sync_progress') {
          const data = event.data || {};
          const eventKey = `${event.file_id}-${event.node_id}`;
          
          if (data.action === 'sync_started' || data.action === 'syncing') {
            setSyncingFiles(prev => {
              if (!prev.includes(event.file_id)) {
                return [...prev, event.file_id];
              }
              return prev;
            });
          }
          
          // Show sync progress notification
          if (data.action === 'sync_started') {
            toast.info(`📡 Starting sync: ${data.file_name} → ${data.target_node?.slice(0, 8)}...`, {
              autoClose: 2000
            });
          }
        }
        
        if (event.event_type === 'sync_completed') {
          const data = event.data || {};
          
          // Remove from syncing files
          setSyncingFiles(prev => prev.filter(id => id !== event.file_id));
          
          // Show completion notification
          toast.success(`✅ Sync completed: ${data.file_name} → ${data.target_node?.slice(0, 8)}...`, {
            autoClose: 3000
          });
          
          // Refresh files list to show updated state
          refreshFiles();
        }
        
        if (event.event_type === 'file_modified') {
          const data = event.data || {};
          
          if (data.action === 'uploaded') {
            // Remove from syncing after upload
            setTimeout(() => {
              setSyncingFiles(prev => prev.filter(id => id !== event.file_id));
            }, 1000);
            
            // Refresh files list
            refreshFiles();
            toast.success(`📁 File uploaded: ${data.file_name}`, {
              autoClose: 3000
            });
          }
        }
        
        if (event.event_type === 'node_status_change') {
          refreshNodes();
          if (event.data?.action === 'registered') {
            toast.success(`🖥️ Node joined: ${event.data.node_name}`, {
              autoClose: 3000
            });
          }
        }
        break;
        
      case 'initial_data':
        setNodes(message.data.nodes || []);
        setFiles(message.data.files || []);
        setMetrics(message.data.metrics || {});
        break;
        
      case 'metrics_update':
        setMetrics(message.data);
        break;
        
      case 'nodes_update':
        setNodes(message.data);
        break;
        
      default:
        console.log('Unknown message type:', message.type);
    }
  };

  const refreshNodes = async () => {
    try {
      const nodesData = await nodeApi.getAll();
      setNodes(nodesData);
    } catch (error) {
      console.error('Error refreshing nodes:', error);
    }
  };

  const refreshFiles = async () => {
    try {
      const filesData = await fileApi.getAll();
      setFiles(filesData);
    } catch (error) {
      console.error('Error refreshing files:', error);
    }
  };

  const refreshMetrics = async () => {
    try {
      const metricsData = await metricsApi.get();
      setMetrics(metricsData);
    } catch (error) {
      console.error('Error refreshing metrics:', error);
    }
  };

  const handleFileUpload = async (uploadedFiles, nodeId) => {
    if (!uploadedFiles || uploadedFiles.length === 0) return;
    
    for (const file of uploadedFiles) {
      try {
        setSyncingFiles(prev => [...prev, `temp_${Date.now()}`]);
        
        await fileApi.upload({
          file: file,
          name: file.name,
          selectedNode: nodeId
        });
        
        toast.success(`File ${file.name} uploaded successfully`);
      } catch (error) {
        console.error('Upload error:', error);
        toast.error(`Failed to upload ${file.name}: ${error.message}`);
      }
    }
    
    // Refresh data
    refreshFiles();
    refreshMetrics();
  };

  const handleUploadComplete = (result) => {
    toast.success('File uploaded and synchronization started!');
    refreshFiles();
    refreshMetrics();
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'nodes', label: 'Nodes', icon: Users },
    { id: 'files', label: 'Files', icon: FileText },
  ];

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 mx-auto text-primary-500 animate-spin mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Loading Dashboard</h2>
          <p className="text-gray-600">Connecting to coordinator...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <RefreshCw className="w-8 h-8 text-primary-600" />
                <h1 className="text-xl font-bold text-gray-900">File Sync Dashboard</h1>
              </div>
              
              {/* Connection Status */}
              <div className="flex items-center space-x-2">
                {isConnected ? (
                  <>
                    <Wifi className="w-4 h-4 text-green-500" />
                    <span className="text-sm text-green-600">Connected</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-4 h-4 text-red-500" />
                    <span className="text-sm text-red-600">Disconnected</span>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-4">
              {/* Quick Stats */}
              <div className="hidden md:flex items-center space-x-6 text-sm">
                <div className="text-center">
                  <p className="font-medium text-gray-900">{nodes.length}</p>
                  <p className="text-gray-500">Nodes</p>
                </div>
                <div className="text-center">
                  <p className="font-medium text-gray-900">{files.length}</p>
                  <p className="text-gray-500">Files</p>
                </div>
                <div className="text-center">
                  <p className="font-medium text-gray-900">{syncingFiles.length}</p>
                  <p className="text-gray-500">Syncing</p>
                </div>
              </div>

              {/* Upload Button */}
              <button
                onClick={() => setIsUploadModalOpen(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                <Upload className="w-4 h-4" />
                <span>Upload File</span>
              </button>

              {/* Refresh Button */}
              <button
                onClick={loadInitialData}
                className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Sync Visualization */}
            <SyncVisualization 
              nodes={nodes} 
              syncEvents={syncEvents} 
              files={files} 
            />
            
            {/* Node Grid */}
            <div>
              <h2 className="text-xl font-semibold text-gray-900 mb-6">Network Nodes</h2>
              {nodes.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border-2 border-dashed border-gray-300">
                  <Users className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No nodes registered</h3>
                  <p className="text-gray-600 mb-4">Register your first node to start synchronizing files</p>
                  <button
                    onClick={() => setActiveTab('nodes')}
                    className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
                  >
                    <Users className="w-4 h-4 mr-2" />
                    Manage Nodes
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {nodes.map((node) => (
                    <NodeCard
                      key={node.node_id}
                      node={node}
                      files={files}
                      onFileUpload={handleFileUpload}
                      syncingFiles={syncingFiles}
                      isSelected={selectedNode === node.node_id}
                      onSelect={setSelectedNode}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'nodes' && (
          <NodeManager 
            nodes={nodes}
            onNodeAdded={refreshNodes}
            onRefresh={refreshNodes}
          />
        )}

        {activeTab === 'files' && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">File Management</h2>
              <button
                onClick={() => setIsUploadModalOpen(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                <Upload className="w-4 h-4" />
                <span>Upload File</span>
              </button>
            </div>
            
            {files.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No files synchronized</h3>
                <p className="text-gray-600">Upload files to see them here</p>
              </div>
            ) : (
              <FileManager 
                files={files}
                nodes={nodes}
                syncingFiles={syncingFiles}
                onFileDeleted={refreshFiles}
              />
            )}
          </div>
        )}
      </main>

      {/* Upload Modal */}
      <FileUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        nodes={nodes}
        onUploadComplete={handleUploadComplete}
      />

      {/* Toast Notifications */}
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
      />
    </div>
  );
}

export default App; 