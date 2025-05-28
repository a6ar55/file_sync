import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import { 
  Upload, 
  X, 
  FileText, 
  AlertCircle, 
  CheckCircle,
  Loader
} from 'lucide-react';
import { fileApi, formatFileSize } from '../utils/api';

const FileUploadModal = ({ isOpen, onClose, nodes, onUploadComplete }) => {
  const [selectedNode, setSelectedNode] = useState('');
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [errors, setErrors] = useState([]);
  const [isUploading, setIsUploading] = useState(false);

  const onDrop = useCallback((acceptedFiles) => {
    const newFiles = acceptedFiles.map(file => ({
      id: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      file,
      name: file.name,
      size: file.size,
      status: 'pending', // pending, uploading, completed, error
      progress: 0,
      error: null
    }));
    
    setUploadedFiles(prev => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    maxSize: 100 * 1024 * 1024 // 100MB max file size
  });

  const removeFile = (fileId) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const uploadFile = async (fileData) => {
    if (!selectedNode) {
      setErrors(prev => [...prev, 'Please select a node first']);
      return;
    }

    try {
      setUploadedFiles(prev => 
        prev.map(f => 
          f.id === fileData.id 
            ? { ...f, status: 'uploading', progress: 0 }
            : f
        )
      );

      const result = await fileApi.upload({
        file: fileData.file,
        name: fileData.name,
        selectedNode: selectedNode
      }, (progress) => {
        setUploadedFiles(prev => 
          prev.map(f => 
            f.id === fileData.id 
              ? { ...f, progress }
              : f
          )
        );
      });

      setUploadedFiles(prev => 
        prev.map(f => 
          f.id === fileData.id 
            ? { ...f, status: 'completed', progress: 100 }
            : f
        )
      );

      // Notify parent component
      if (onUploadComplete) {
        onUploadComplete(result);
      }

    } catch (error) {
      console.error('Upload error:', error);
      setUploadedFiles(prev => 
        prev.map(f => 
          f.id === fileData.id 
            ? { ...f, status: 'error', error: error.message }
            : f
        )
      );
      setErrors(prev => [...prev, `Failed to upload ${fileData.name}: ${error.message}`]);
    }
  };

  const uploadAllFiles = async () => {
    if (!selectedNode) {
      setErrors(prev => [...prev, 'Please select a node first']);
      return;
    }

    if (uploadedFiles.length === 0) {
      setErrors(prev => [...prev, 'No files to upload']);
      return;
    }

    setIsUploading(true);
    setErrors([]);

    for (const file of uploadedFiles.filter(f => f.status === 'pending')) {
      await uploadFile(file);
    }

    setIsUploading(false);
  };

  const resetModal = () => {
    setUploadedFiles([]);
    setErrors([]);
    setUploadProgress({});
    setSelectedNode('');
    setIsUploading(false);
  };

  const handleClose = () => {
    resetModal();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && handleClose()}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Upload Files</h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {/* Node Selection */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Target Node
            </label>
            <select
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="">Choose a node...</option>
              {nodes.filter(n => n.status === 'online').map(node => (
                <option key={node.node_id} value={node.node_id}>
                  {node.name || node.node_id} ({node.address}:{node.port})
                </option>
              ))}
            </select>
          </div>

          {/* Drag and Drop Area */}
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 cursor-pointer ${
              isDragActive
                ? 'border-primary-400 bg-primary-50'
                : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
            {isDragActive ? (
              <p className="text-primary-600 font-medium">Drop files here...</p>
            ) : (
              <div>
                <p className="text-gray-600 font-medium mb-2">
                  Drag & drop files here, or click to select
                </p>
                <p className="text-sm text-gray-500">
                  Files will be synchronized across all nodes
                </p>
              </div>
            )}
          </div>

          {/* Error Messages */}
          {errors.length > 0 && (
            <div className="mt-4 space-y-2">
              {errors.map((error, index) => (
                <div key={index} className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                  <span className="text-sm text-red-700">{error}</span>
                </div>
              ))}
            </div>
          )}

          {/* File List */}
          {uploadedFiles.length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">
                Files to Upload ({uploadedFiles.length})
              </h3>
              <div className="space-y-3 max-h-60 overflow-y-auto">
                {uploadedFiles.map((file) => (
                  <motion.div
                    key={file.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border"
                  >
                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                      <FileText className="w-5 h-5 text-gray-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {file.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      {/* Status Icon */}
                      {file.status === 'pending' && (
                        <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center">
                          <div className="w-2 h-2 bg-gray-400 rounded-full" />
                        </div>
                      )}
                      {file.status === 'uploading' && (
                        <div className="flex items-center space-x-2">
                          <Loader className="w-4 h-4 text-blue-500 animate-spin" />
                          <span className="text-xs text-blue-600">{file.progress}%</span>
                        </div>
                      )}
                      {file.status === 'completed' && (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      )}
                      {file.status === 'error' && (
                        <AlertCircle className="w-5 h-5 text-red-500" />
                      )}

                      {/* Remove Button */}
                      {file.status !== 'uploading' && (
                        <button
                          onClick={() => removeFile(file.id)}
                          className="text-gray-400 hover:text-red-500 transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>

                    {/* Progress Bar */}
                    {file.status === 'uploading' && (
                      <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200 rounded-b">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${file.progress}%` }}
                          className="h-full bg-blue-500 rounded-b"
                        />
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
          <button
            onClick={resetModal}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Clear All
          </button>
          <div className="flex space-x-3">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={uploadAllFiles}
              disabled={isUploading || uploadedFiles.length === 0 || !selectedNode}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
            >
              {isUploading && <Loader className="w-4 h-4 animate-spin" />}
              <span>
                {isUploading ? 'Uploading...' : `Upload ${uploadedFiles.length} file${uploadedFiles.length !== 1 ? 's' : ''}`}
              </span>
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default FileUploadModal;