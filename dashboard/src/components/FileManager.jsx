import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileText, 
  Trash2, 
  Download,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Server,
  Calendar,
  HardDrive,
  Edit3,
  Eye
} from 'lucide-react';
import { fileApi } from '../utils/api';
import { formatFileSize, formatDate } from '../utils/api';
import { toast } from 'react-toastify';

const FileManager = ({ files, nodes, syncingFiles, onFileDeleted, onFileEdit }) => {
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState('asc');
  const [filterNode, setFilterNode] = useState('all');

  // Filter and sort files
  const filteredFiles = files.filter(file => {
    if (filterNode === 'all') return true;
    return file.owner_node === filterNode;
  });

  const sortedFiles = [...filteredFiles].sort((a, b) => {
    let aVal, bVal;
    
    switch (sortBy) {
      case 'name':
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case 'size':
        aVal = a.size || 0;
        bVal = b.size || 0;
        break;
      case 'modified':
        aVal = new Date(a.modified_at);
        bVal = new Date(b.modified_at);
        break;
      case 'owner':
        aVal = a.owner_node.toLowerCase();
        bVal = b.owner_node.toLowerCase();
        break;
      default:
        return 0;
    }
    
    if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });

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
    if (selectedFiles.size === sortedFiles.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(sortedFiles.map(f => f.file_id)));
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedFiles.size === 0) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete ${selectedFiles.size} selected file(s)? This action cannot be undone.`
    );

    if (!confirmed) return;

    setIsDeleting(true);
    try {
      let successCount = 0;
      let errorCount = 0;

      for (const fileId of selectedFiles) {
        try {
          const file = files.find(f => f.file_id === fileId);
          if (file) {
            await fileApi.delete(fileId, file.owner_node);
            successCount++;
          }
        } catch (error) {
          console.error(`Error deleting file ${fileId}:`, error);
          errorCount++;
        }
      }

      if (successCount > 0) {
        toast.success(`Successfully deleted ${successCount} file(s)`);
      }
      if (errorCount > 0) {
        toast.error(`Failed to delete ${errorCount} file(s)`);
      }

      setSelectedFiles(new Set());
      if (onFileDeleted) {
        onFileDeleted();
      }
    } catch (error) {
      console.error('Error deleting files:', error);
      toast.error('Failed to delete files');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const getNodeName = (nodeId) => {
    const node = nodes.find(n => n.node_id === nodeId);
    return node?.name || nodeId;
  };

  const handleDownload = async (file) => {
    try {
      const response = await fileApi.download(file.file_id);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Downloaded ${file.name}`);
    } catch (error) {
      console.error('Download error:', error);
      toast.error(`Failed to download ${file.name}`);
    }
  };

  const handleEdit = (file) => {
    if (onFileEdit) {
      onFileEdit(file);
    }
  };

  const SortButton = ({ field, children }) => (
    <button
      onClick={() => handleSort(field)}
      className={`flex items-center space-x-1 text-sm font-medium transition-colors ${
        sortBy === field 
          ? 'text-blue-600' 
          : 'text-gray-600 hover:text-gray-900'
      }`}
    >
      <span>{children}</span>
      {sortBy === field && (
        <span className="text-xs">
          {sortOrder === 'asc' ? '↑' : '↓'}
        </span>
      )}
    </button>
  );

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          {/* Select All */}
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={selectedFiles.size === sortedFiles.length && sortedFiles.length > 0}
              onChange={handleSelectAll}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-600">
              Select All ({selectedFiles.size} selected)
            </span>
          </div>

          {/* Filter by Node */}
          <select
            value={filterNode}
            onChange={(e) => setFilterNode(e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-3 py-1 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Nodes</option>
            {nodes.map(node => (
              <option key={node.node_id} value={node.node_id}>
                {getNodeName(node.node_id)}
              </option>
            ))}
          </select>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2">
          {selectedFiles.size > 0 && (
            <button
              onClick={handleDeleteSelected}
              disabled={isDeleting}
              className="flex items-center space-x-1 px-3 py-1 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 transition-colors text-sm"
            >
              {isDeleting ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              <span>Delete ({selectedFiles.size})</span>
            </button>
          )}
        </div>
      </div>

      {/* Table Header */}
      <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
        <div className="grid grid-cols-12 gap-4 items-center text-sm font-medium text-gray-700">
          <div className="col-span-1"></div>
          <div className="col-span-3">
            <SortButton field="name">Name</SortButton>
          </div>
          <div className="col-span-2">
            <SortButton field="size">Size</SortButton>
          </div>
          <div className="col-span-2">
            <SortButton field="owner">Owner</SortButton>
          </div>
          <div className="col-span-2">
            <SortButton field="modified">Modified</SortButton>
          </div>
          <div className="col-span-1">Status</div>
          <div className="col-span-1">Actions</div>
        </div>
      </div>

      {/* File List */}
      <div className="space-y-2">
        <AnimatePresence>
          {sortedFiles.map((file) => (
            <motion.div
              key={file.file_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={`p-3 border rounded-lg transition-all ${
                selectedFiles.has(file.file_id)
                  ? 'border-blue-300 bg-blue-50'
                  : syncingFiles.includes(file.file_id)
                  ? 'border-blue-200 bg-blue-25'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="grid grid-cols-12 gap-4 items-center">
                {/* Checkbox */}
                <div className="col-span-1">
                  <input
                    type="checkbox"
                    checked={selectedFiles.has(file.file_id)}
                    onChange={() => handleFileSelect(file.file_id)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                </div>

                {/* File Info */}
                <div className="col-span-3">
                  <div className="flex items-center space-x-3">
                    <FileText className={`w-5 h-5 flex-shrink-0 ${
                      syncingFiles.includes(file.file_id) ? 'text-blue-500' : 'text-gray-500'
                    }`} />
                    <div className="min-w-0 flex-1">
                      <h4 className="font-medium text-gray-900 truncate">
                        {file.name}
                      </h4>
                      <p className="text-xs text-gray-500 truncate">
                        v{file.version} • {file.path}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Size */}
                <div className="col-span-2">
                  <span className="text-sm text-gray-600">
                    {formatFileSize(file.size)}
                  </span>
                </div>

                {/* Owner */}
                <div className="col-span-2">
                  <div className="flex items-center space-x-2">
                    <Server className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600 truncate">
                      {getNodeName(file.owner_node)}
                    </span>
                  </div>
                </div>

                {/* Modified */}
                <div className="col-span-2">
                  <div className="flex items-center space-x-1">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">
                      {formatDate(file.modified_at)}
                    </span>
                  </div>
                </div>

                {/* Status */}
                <div className="col-span-1">
                  {syncingFiles.includes(file.file_id) ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      className="flex items-center justify-center"
                    >
                      <RefreshCw className="w-4 h-4 text-blue-500" />
                    </motion.div>
                  ) : (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  )}
                </div>

                {/* Actions */}
                <div className="col-span-1 flex items-center justify-end space-x-1">
                  {syncingFiles.includes(file.file_id) ? (
                    <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />
                  ) : (
                    <>
                      <button
                        onClick={() => handleEdit(file)}
                        className="p-1 text-gray-500 hover:text-green-600 transition-colors"
                        title="Edit File"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDownload(file)}
                        className="p-1 text-gray-500 hover:text-blue-600 transition-colors"
                        title="Download"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Summary */}
      <div className="border-t border-gray-200 pt-4">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            Showing {sortedFiles.length} of {files.length} files
          </span>
          <span>
            Total size: {formatFileSize(sortedFiles.reduce((sum, file) => sum + (file.size || 0), 0))}
          </span>
        </div>
      </div>
    </div>
  );
};

export default FileManager; 