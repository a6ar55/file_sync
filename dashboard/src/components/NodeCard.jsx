import React from 'react';
import { motion } from 'framer-motion';
import { 
  Server, 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  FileText, 
  HardDrive, 
  Clock 
} from 'lucide-react';
import { formatFileSize, formatDate } from '../utils/api';

const NodeCard = ({ 
  node, 
  files, 
  onFileUpload, 
  syncingFiles, 
  isSelected, 
  onSelect 
}) => {
  const getStatusIcon = () => {
    switch (node.status) {
      case 'online':
        return <Wifi className="w-5 h-5 text-green-500" />;
      case 'syncing':
        return <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <WifiOff className="w-5 h-5 text-red-500" />;
    }
  };

  const getStatusColor = () => {
    switch (node.status) {
      case 'online':
        return 'border-green-400 bg-green-50';
      case 'syncing':
        return 'border-blue-400 bg-blue-50';
      case 'offline':
        return 'border-red-400 bg-red-50';
      default:
        return 'border-gray-300 bg-gray-50';
    }
  };

  const nodeFiles = files.filter(file => file.owner_node === node.node_id);
  const totalSize = nodeFiles.reduce((sum, file) => sum + (file.size || 0), 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`node-card ${getStatusColor()} ${
        isSelected ? 'ring-2 ring-primary-500' : ''
      } cursor-pointer transition-all duration-200 hover:shadow-lg`}
      onClick={() => onSelect && onSelect(node.node_id)}
    >
      {/* Node Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-gray-100 rounded-lg">
            <Server className="w-6 h-6 text-gray-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{node.name || node.node_id}</h3>
            <p className="text-sm text-gray-500">{node.address}:{node.port}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <span className={`text-sm font-medium ${
            node.status === 'online' ? 'text-green-600' : 
            node.status === 'syncing' ? 'text-blue-600' : 'text-red-600'
          }`}>
            {node.status?.toUpperCase() || 'UNKNOWN'}
          </span>
        </div>
      </div>

      {/* Node Stats */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="flex items-center space-x-2">
          <FileText className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-600">
            {nodeFiles.length} file{nodeFiles.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <HardDrive className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-600">
            {formatFileSize(totalSize)}
          </span>
        </div>
      </div>

      {/* Last Seen */}
      <div className="flex items-center space-x-2 mb-4">
        <Clock className="w-4 h-4 text-gray-500" />
        <span className="text-xs text-gray-500">
          Last seen: {formatDate(node.last_seen)}
        </span>
      </div>

      {/* File Upload Area */}
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-primary-400 transition-colors">
        <input
          type="file"
          multiple
          onChange={(e) => onFileUpload(e.files || e.target.files, node.node_id)}
          className="hidden"
          id={`file-upload-${node.node_id}`}
        />
        <label 
          htmlFor={`file-upload-${node.node_id}`}
          className="cursor-pointer block"
        >
          <div className="text-gray-600 hover:text-primary-600 transition-colors">
            <FileText className="w-8 h-8 mx-auto mb-2" />
            <p className="text-sm font-medium">Drop files or click to upload</p>
            <p className="text-xs text-gray-500 mt-1">Files will be synced to all nodes</p>
          </div>
        </label>
      </div>

      {/* Files List */}
      {nodeFiles.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Files:</h4>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {nodeFiles.map((file) => {
              const isSyncing = syncingFiles.includes(file.file_id);
              return (
                <motion.div
                  key={file.file_id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`flex items-center justify-between p-2 rounded text-xs ${
                    isSyncing 
                      ? 'bg-blue-100 border border-blue-300' 
                      : 'bg-gray-100'
                  }`}
                >
                  <div className="flex items-center space-x-2 flex-1 min-w-0">
                    <FileText className={`w-3 h-3 flex-shrink-0 ${
                      isSyncing ? 'text-blue-500' : 'text-gray-500'
                    }`} />
                    <span className="truncate font-medium">{file.name}</span>
                    {isSyncing && (
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      >
                        <RefreshCw className="w-3 h-3 text-blue-500" />
                      </motion.div>
                    )}
                  </div>
                  <span className="text-gray-500 ml-2">
                    {formatFileSize(file.size)}
                  </span>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* Node Capabilities */}
      {node.capabilities && node.capabilities.length > 0 && (
        <div className="mt-4">
          <div className="flex flex-wrap gap-1">
            {node.capabilities.map((capability) => (
              <span
                key={capability}
                className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-primary-100 text-primary-800"
              >
                {capability}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default NodeCard; 