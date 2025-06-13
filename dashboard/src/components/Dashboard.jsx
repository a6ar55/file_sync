import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import NodeManager from './NodeManager';
import FileManager from './FileManager';
import SyncVisualization from './SyncVisualization';
import NetworkTopology from './NetworkTopology';
import VectorClockVisualization from './VectorClockVisualization';
import DeltaSyncDashboard from './DeltaSyncDashboard';
import DeltaSyncVisualization from './DeltaSyncVisualization';
import FileEditor from './FileEditor';
import MultiNodeEditor from './MultiNodeEditor';
import { 
  Network, 
  Clock, 
  Database, 
  Activity, 
  BarChart3,
  Layers,
  RefreshCw,
  Edit
} from 'lucide-react';

const Dashboard = () => {
  const [nodes, setNodes] = useState([]);
  const [files, setFiles] = useState([]);
  const [syncEvents, setSyncEvents] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [activeTab, setActiveTab] = useState('overview');
  const [isConnected, setIsConnected] = useState(false);
  const [editingFile, setEditingFile] = useState(null);

  useEffect(() => {
    // Fetch initial data
    fetchNodes();
    fetchFiles();
    fetchEvents();
    fetchMetrics();

    // Setup WebSocket connection for real-time updates
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/ws`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      setIsConnected(true);
    };
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        if (message.type === 'event') {
          // Add new event to the list
          setSyncEvents(prev => [message.data, ...prev.slice(0, 99)]);
        } else if (message.type === 'initial_data') {
          // Handle initial data from server
          if (message.data.nodes) setNodes(message.data.nodes);
          if (message.data.files) setFiles(message.data.files);
          if (message.data.metrics) setMetrics(message.data.metrics);
        } else if (message.type === 'nodes_update') {
          setNodes(message.data);
        } else if (message.type === 'files_update') {
          setFiles(message.data);
        } else if (message.type === 'metrics_update') {
          setMetrics(message.data);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
    
    ws.onclose = () => {
      setIsConnected(false);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    // Cleanup on unmount
    return () => {
      ws.close();
    };
  }, []);

  const fetchNodes = async () => {
    try {
      const response = await fetch('/api/nodes');
      if (response.ok) {
        const data = await response.json();
        setNodes(data);
      }
    } catch (error) {
      console.error('Failed to fetch nodes:', error);
    }
  };

  const fetchFiles = async () => {
    try {
      const response = await fetch('/api/files');
      if (response.ok) {
        const data = await response.json();
        setFiles(data);
      }
    } catch (error) {
      console.error('Failed to fetch files:', error);
    }
  };

  const fetchEvents = async () => {
    try {
      const response = await fetch('/api/events?limit=50');
      if (response.ok) {
        const data = await response.json();
        setSyncEvents(data);
      }
    } catch (error) {
      console.error('Failed to fetch events:', error);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await fetch('/api/metrics');
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  };

  const tabs = [
    { id: 'overview', name: 'Overview', icon: Activity },
    { id: 'topology', name: 'Network Topology', icon: Network },
    { id: 'vector-clocks', name: 'Vector Clocks', icon: Clock },
    { id: 'editor', name: 'File Editor', icon: Edit },
    { id: 'delta-sync', name: 'Delta Sync', icon: Layers },
    { id: 'sync-monitor', name: 'Sync Monitor', icon: Database },
    { id: 'performance', name: 'Performance', icon: BarChart3 }
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <NodeManager 
                nodes={nodes} 
                onNodesChange={fetchNodes}
                onFilesChange={fetchFiles} 
              />
              <FileManager 
                files={files} 
                nodes={nodes}
                onFilesChange={fetchFiles}
                onFileEdit={setEditingFile}
              />
            </div>
            <SyncVisualization 
              nodes={nodes} 
              syncEvents={syncEvents}
              files={files}
            />
          </div>
        );
      
      case 'topology':
        return (
          <NetworkTopology 
            nodes={nodes} 
            syncEvents={syncEvents}
          />
        );
      
      case 'vector-clocks':
        return (
          <VectorClockVisualization 
            events={syncEvents}
          />
        );
      
      case 'editor':
        return (
          <FileEditor />
        );
      
      case 'delta-sync':
        return (
          <DeltaSyncVisualization />
        );
      
      case 'sync-monitor':
        return (
          <SyncVisualization 
            nodes={nodes} 
            syncEvents={syncEvents}
            files={files}
          />
        );
      
      case 'performance':
        return (
          <div className="space-y-6">
            <DeltaSyncDashboard />
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">System Metrics</h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-blue-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {metrics.registered_nodes || 0}
                  </div>
                  <div className="text-sm text-blue-700">Registered Nodes</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {metrics.total_files || 0}
                  </div>
                  <div className="text-sm text-green-700">Total Files</div>
                </div>
                <div className="bg-yellow-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-yellow-600">
                    {metrics.active_connections || 0}
                  </div>
                  <div className="text-sm text-yellow-700">Active Connections</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {(metrics.average_sync_latency || 0).toFixed(3)}s
                  </div>
                  <div className="text-sm text-purple-700">Avg Sync Latency</div>
                </div>
              </div>
            </div>
          </div>
        );
      
      default:
        return <div>Tab content not found</div>;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-semibold text-gray-900">
                Distributed File Sync Dashboard
              </h1>
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-medium ${
                isConnected 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-green-600' : 'bg-red-600'
                }`}></div>
                <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <button
                onClick={() => {
                  fetchNodes();
                  fetchFiles();
                  fetchEvents();
                  fetchMetrics();
                }}
                className="flex items-center space-x-2 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Refresh</span>
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
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {renderTabContent()}
        </motion.div>
      </main>

      {/* Status Bar */}
      <footer className="bg-white border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <div className="flex items-center space-x-6">
              <span>Nodes: {nodes.filter(n => n.status === 'online').length}/{nodes.length}</span>
              <span>Files: {files.filter(f => !f.is_deleted).length}</span>
              <span>Events: {syncEvents.length}</span>
            </div>
            <div className="flex items-center space-x-2">
              <span>Last Updated: {new Date().toLocaleTimeString()}</span>
            </div>
          </div>
        </div>
      </footer>

      {/* Multi-Node Editor Modal */}
      <MultiNodeEditor
        file={editingFile}
        nodes={nodes}
        isOpen={!!editingFile}
        onClose={() => setEditingFile(null)}
        onFileSaved={() => {
          fetchFiles();
          fetchEvents();
        }}
      />
    </div>
  );
};

export default Dashboard; 