import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  X, 
  Server, 
  FileText, 
  Trash2, 
  Download,
  RefreshCw,
  HardDrive,
  Calendar,
  User,
  Wifi,
  WifiOff
} from 'lucide-react';
import { fileApi } from '../utils/api';
import { formatFileSize, formatDate } from '../utils/api';
import { toast } from 'react-toastify';

const NodeDetailModal = ({ isOpen, onClose, node, onFileDeleted }) => {
  const [files, setFiles] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState(new Set());

  useEffect(() => {
    if (isOpen && node) {
      loadNodeFiles();
    }
  }, [isOpen, node]);

  const loadNodeFiles = async () => {
    if (!node) return;
    
    setIsLoading(true);
    try {
      const nodeFiles = await fileApi.getByNode(node.node_id);
      setFiles(nodeFiles);
    } catch (error) {
      console.error('Error loading node files:', error);
      toast.error('Failed to load node files');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = (fileId) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(fileId)) {
      newSelected.delete(fileId);
    } else {
      newSelected.add(fileId);
    }
    setSelectedFiles(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(files.map(f => f.file_id)));
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedFiles.size === 0) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete ${selectedFiles.size} selected file(s)? This action cannot be undone.`
    );

    if (!confirmed) return;

    try {
      for (const fileId of selectedFiles) {
        await fileApi.delete(fileId, node.node_id);
      }
      
      toast.success(`Successfully deleted ${selectedFiles.size} file(s)`);
      setSelectedFiles(new Set());
      loadNodeFiles();
      
      if (onFileDeleted) {
        onFileDeleted();
      }
    } catch (error) {
      console.error('Error deleting files:', error);
      toast.error('Failed to delete some files');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'online': return 'text-green-600 bg-green-100';
      case 'syncing': return 'text-blue-600 bg-blue-100';
      case 'offline': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'online': return <Wifi className="w-4 h-4" />;
      case 'offline': return <WifiOff className="w-4 h-4" />;
      default: return <Server className="w-4 h-4" />;
    }
  };

  if (!isOpen || !node) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden"
        >
          {/* Header */}
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className={`p-2 rounded-lg ${getStatusColor(node.status)}`}>
                  {getStatusIcon(node.status)}
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    {node.name || node.node_id}
                  </h2>
                  <p className="text-sm text-gray-600">
                    Node ID: {node.node_id}
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>

          {/* Node Info */}
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${
                  node.status === 'online' ? 'bg-green-500' : 
                  node.status === 'syncing' ? 'bg-blue-500' : 'bg-red-500'
                }`}></div>
                <span className="text-sm font-medium capitalize">{node.status}</span>
              </div>
              
              <div className="flex items-center space-x-2 text-gray-600">
                <HardDrive className="w-4 h-4" />
                <span className="text-sm">{files.length} files</span>
              </div>
              
              <div className="flex items-center space-x-2 text-gray-600">
                <User className="w-4 h-4" />
                <span className="text-sm">{node.address}:{node.port}</span>
              </div>
              
              <div className="flex items-center space-x-2 text-gray-600">
                <Calendar className="w-4 h-4" />
                <span className="text-sm">
                  {formatDate(node.last_seen)}
                </span>
              </div>
            </div>
          </div>

          {/* Files Section */}
          <div className="flex-1 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900">
                  Files on this Node ({files.length})
                </h3>
                <div className="flex items-center space-x-2">
                  {selectedFiles.size > 0 && (
                    <button
                      onClick={handleDeleteSelected}
                      className="flex items-center space-x-1 px-3 py-1 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>Delete ({selectedFiles.size})</span>
                    </button>
                  )}
                  <button
                    onClick={loadNodeFiles}
                    className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
                    disabled={isLoading}
                  >
                    <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 max-h-96 overflow-y-auto">
              {isLoading ? (
                <div className="text-center py-8">
                  <RefreshCw className="w-8 h-8 mx-auto text-gray-400 animate-spin mb-2" />
                  <p className="text-gray-500">Loading files...</p>
                </div>
              ) : files.length === 0 ? (
                <div className="text-center py-8">
                  <FileText className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                  <h4 className="text-lg font-medium text-gray-900 mb-2">No files found</h4>
                  <p className="text-gray-600">This node doesn't have any files yet</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {/* Select All Checkbox */}
                  <div className="flex items-center space-x-2 py-2 border-b border-gray-100">
                    <input
                      type="checkbox"
                      checked={selectedFiles.size === files.length && files.length > 0}
                      onChange={handleSelectAll}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-600">
                      Select All ({selectedFiles.size} selected)
                    </span>
                  </div>

                  {/* File List */}
                  {files.map((file) => (
                    <motion.div
                      key={file.file_id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`p-3 border rounded-lg transition-all ${
                        selectedFiles.has(file.file_id)
                          ? 'border-blue-300 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <input
                          type="checkbox"
                          checked={selectedFiles.has(file.file_id)}
                          onChange={() => handleFileSelect(file.file_id)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        
                        <FileText className="w-5 h-5 text-gray-500 flex-shrink-0" />
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <h4 className="font-medium text-gray-900 truncate">
                              {file.name}
                            </h4>
                            <span className="text-sm text-gray-500 ml-2">
                              v{file.version}
                            </span>
                          </div>
                          
                          <div className="flex items-center space-x-4 text-xs text-gray-500 mt-1">
                            <span>{formatFileSize(file.size)}</span>
                            <span>{formatDate(file.modified_at)}</span>
                            <span className="truncate max-w-32">{file.path}</span>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">
                Total storage: {formatFileSize(files.reduce((sum, file) => sum + file.size, 0))}
              </div>
              <button
                onClick={onClose}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default NodeDetailModal; 