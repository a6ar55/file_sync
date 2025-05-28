import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Plus, 
  Server, 
  Trash2, 
  AlertCircle,
  CheckCircle,
  Loader,
  Eye,
  Wifi,
  WifiOff,
  HardDrive,
  Calendar
} from 'lucide-react';
import { nodeApi, fileApi } from '../utils/api';
import { formatDate } from '../utils/api';
import NodeDetailModal from './NodeDetailModal';

const NodeManager = ({ nodes, onNodeAdded, onNodeRemoved, onRefresh }) => {
  const [showForm, setShowForm] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [showNodeDetail, setShowNodeDetail] = useState(false);
  const [formData, setFormData] = useState({
    node_id: '',
    name: '',
    address: 'localhost',
    port: 8001,
    watch_directories: ['/tmp/sync']
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      const response = await nodeApi.register({
        ...formData,
        capabilities: ['sync', 'upload', 'download']
      });

      if (onNodeAdded) {
        onNodeAdded(response);
      }

      // Reset form
      setFormData({
        node_id: '',
        name: '',
        address: 'localhost',
        port: 8001,
        watch_directories: ['/tmp/sync']
      });
      setShowForm(false);
    } catch (error) {
      setError(error.response?.data?.detail || error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const addTestNode = async () => {
    setIsSubmitting(true);
    setError('');

    try {
      const testNodeData = {
        node_id: `test_node_${Date.now()}`,
        name: `Test Node ${Math.floor(Math.random() * 100)}`,
        address: 'localhost',
        port: 8001 + Math.floor(Math.random() * 100),
        watch_directories: ['/tmp/sync'],
        capabilities: ['sync', 'upload', 'download']
      };

      const response = await nodeApi.register(testNodeData);

      if (onNodeAdded) {
        onNodeAdded(response);
      }
    } catch (error) {
      setError(error.response?.data?.detail || error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'port' ? parseInt(value) : value
    }));
  };

  const handleViewNodeDetails = (node) => {
    setSelectedNode(node);
    setShowNodeDetail(true);
  };

  const handleCloseNodeDetail = () => {
    setShowNodeDetail(false);
    setSelectedNode(null);
  };

  const handleFileDeleted = () => {
    if (onRefresh) {
      onRefresh();
    }
  };

  const handleRemoveNode = async (nodeId) => {
    if (!window.confirm('Are you sure you want to remove this node? This action cannot be undone.')) {
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      await nodeApi.remove(nodeId);
      
      if (onNodeRemoved) {
        onNodeRemoved(nodeId);
      }
      
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      setError(error.response?.data?.detail || error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'online': return 'text-green-600 bg-green-100 border-green-200';
      case 'syncing': return 'text-blue-600 bg-blue-100 border-blue-200';
      case 'offline': return 'text-red-600 bg-red-100 border-red-200';
      default: return 'text-gray-600 bg-gray-100 border-gray-200';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'online': return <Wifi className="w-4 h-4" />;
      case 'offline': return <WifiOff className="w-4 h-4" />;
      default: return <Server className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Node Management</h2>
        <div className="flex space-x-3">
          <button
            onClick={addTestNode}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
          >
            {isSubmitting && <Loader className="w-4 h-4 animate-spin" />}
            <Plus className="w-4 h-4" />
            <span>Add Test Node</span>
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Add Node</span>
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg"
        >
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-sm text-red-700">{error}</span>
        </motion.div>
      )}

      {/* Add Node Form */}
      {showForm && (
        <motion.form
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          onSubmit={handleSubmit}
          className="bg-gray-50 rounded-lg p-6 space-y-4"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Node ID
              </label>
              <input
                type="text"
                name="node_id"
                value={formData.node_id}
                onChange={handleInputChange}
                required
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="node_001"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Node Name
              </label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                required
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="My Sync Node"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Address
              </label>
              <input
                type="text"
                name="address"
                value={formData.address}
                onChange={handleInputChange}
                required
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Port
              </label>
              <input
                type="number"
                name="port"
                value={formData.port}
                onChange={handleInputChange}
                required
                min="1"
                max="65535"
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
          </div>
          
          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
            >
              {isSubmitting && <Loader className="w-4 h-4 animate-spin" />}
              <span>Add Node</span>
            </button>
          </div>
        </motion.form>
      )}

      {/* Nodes List */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">
            Registered Nodes ({nodes.length})
          </h3>
        </div>
        
        {nodes.length === 0 ? (
          <div className="text-center py-12">
            <Server className="w-12 h-12 mx-auto text-gray-400 mb-4" />
            <h4 className="text-lg font-medium text-gray-900 mb-2">No nodes registered</h4>
            <p className="text-gray-600">Add your first node to start synchronizing files</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {nodes.map((node) => (
              <motion.div
                key={node.node_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-6 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className={`p-3 rounded-lg border ${getStatusColor(node.status)}`}>
                      {getStatusIcon(node.status)}
                    </div>
                    
                    <div className="flex-1">
                      <div className="flex items-center space-x-3">
                        <h4 className="text-lg font-medium text-gray-900">
                          {node.name || node.node_id}
                        </h4>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(node.status)}`}>
                          {node.status}
                        </span>
                      </div>
                      
                      <div className="mt-1 flex items-center space-x-6 text-sm text-gray-600">
                        <span>ID: {node.node_id}</span>
                        <span>📍 {node.address}:{node.port}</span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4" />
                          <span>Last seen: {formatDate(node.last_seen)}</span>
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleViewNodeDetails(node)}
                      className="flex items-center space-x-1 px-3 py-1 text-sm font-medium text-blue-600 bg-blue-100 rounded-lg hover:bg-blue-200 transition-colors"
                    >
                      <Eye className="w-4 h-4" />
                      <span>View Details</span>
                    </button>
                    
                    <button
                      onClick={() => handleRemoveNode(node.node_id)}
                      disabled={isSubmitting}
                      className="flex items-center space-x-1 px-3 py-1 text-sm font-medium text-red-600 bg-red-100 rounded-lg hover:bg-red-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>Remove</span>
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Node Detail Modal */}
      <NodeDetailModal
        isOpen={showNodeDetail}
        onClose={handleCloseNodeDetail}
        node={selectedNode}
        onFileDeleted={handleFileDeleted}
      />
    </div>
  );
};

export default NodeManager; 