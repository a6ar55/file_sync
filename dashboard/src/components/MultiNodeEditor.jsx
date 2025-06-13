import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { X, Save, Edit3, Users, Zap, Server, Clock, RefreshCw } from 'lucide-react';
import { toast } from 'react-toastify';

const MultiNodeEditor = ({ file, nodes, isOpen, onClose, onFileSaved }) => {
  const [fileContent, setFileContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [activeNode, setActiveNode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [deltaMetrics, setDeltaMetrics] = useState(null);
  const [lastSyncTime, setLastSyncTime] = useState(null);

  useEffect(() => {
    if (isOpen && file) {
      loadFileContent();
    }
  }, [isOpen, file]);

  const loadFileContent = async () => {
    if (!file) return;
    setIsLoading(true);
    try {
      const response = await fetch(`/api/files/${file.file_id}/content`);
      if (response.ok) {
        const data = await response.json();
        const content = hexToString(data.content);
        setFileContent(content);
        setOriginalContent(content);
        setActiveNode(file.owner_node);
      } else {
        toast.error('Failed to load file content');
      }
    } catch (error) {
      toast.error('Error loading file content');
    } finally {
      setIsLoading(false);
    }
  };

  const saveFile = async () => {
    if (!file || fileContent === originalContent) return;
    setIsSaving(true);
    const startTime = Date.now();
    
    try {
      const chunks = createChunks(fileContent);
      const fileMetadata = {
        ...file,
        size: fileContent.length,
        modified_at: new Date().toISOString(),
        owner_node: activeNode
      };

      const response = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_metadata: fileMetadata,
          chunks: chunks,
          vector_clock: { clocks: { [activeNode]: Date.now() } },
          use_delta_sync: true
        })
      });

      if (response.ok) {
        const result = await response.json();
        const syncTime = Date.now() - startTime;
        
        setDeltaMetrics({
          ...result.delta_metrics,
          sync_time: syncTime / 1000,
          active_node: activeNode
        });
        
        setOriginalContent(fileContent);
        setLastSyncTime(new Date());
        
        if (onFileSaved) onFileSaved();
        toast.success(`File saved from ${getNodeName(activeNode)} - Changes synced to all nodes!`);
      } else {
        toast.error('Failed to save file');
      }
    } catch (error) {
      toast.error('Error saving file');
    } finally {
      setIsSaving(false);
    }
  };

  const createChunks = (content) => {
    const chunks = [];
    const chunkSize = 1024;
    const bytes = new TextEncoder().encode(content);
    
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.slice(i, Math.min(i + chunkSize, bytes.length));
      chunks.push({
        index: chunks.length,
        offset: i,
        size: chunk.length,
        hash: '',
        data: Array.from(chunk).map(b => b.toString(16).padStart(2, '0')).join('')
      });
    }
    return chunks;
  };

  const hexToString = (hex) => {
    const bytes = [];
    for (let i = 0; i < hex.length; i += 2) {
      bytes.push(parseInt(hex.substr(i, 2), 16));
    }
    return new TextDecoder().decode(new Uint8Array(bytes));
  };

  const getNodeName = (nodeId) => {
    const node = nodes.find(n => n.node_id === nodeId);
    return node?.name || nodeId;
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  if (!isOpen || !file) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-lg shadow-2xl w-full max-w-5xl h-5/6 flex flex-col"
      >
        <div className="border-b border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Edit3 className="w-6 h-6 text-blue-600" />
              <h2 className="text-xl font-semibold text-gray-900">{file.name}</h2>
              <div className="flex items-center space-x-2 text-sm text-gray-500">
                <Users className="w-4 h-4" />
                <span>Multi-node editing</span>
              </div>
            </div>
            <button onClick={onClose} className="p-2 text-gray-500 hover:text-gray-700">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 flex flex-col p-6">
          {deltaMetrics && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg p-4 mb-4"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold text-green-800 flex items-center">
                  <Zap className="w-5 h-5 mr-2" />
                  Delta Sync Results
                </h3>
                <div className="flex items-center space-x-2 text-sm text-green-600">
                  <Server className="w-4 h-4" />
                  <span>From {getNodeName(deltaMetrics.active_node)}</span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {deltaMetrics.compression_ratio?.toFixed(1) || 0}%
                  </div>
                  <div className="text-sm text-gray-600">Efficiency</div>
                </div>
                <div className="bg-white rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {formatBytes(deltaMetrics.bandwidth_saved || 0)}
                  </div>
                  <div className="text-sm text-gray-600">Saved</div>
                </div>
                <div className="bg-white rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {deltaMetrics.chunks_unchanged || 0}
                  </div>
                  <div className="text-sm text-gray-600">Reused Chunks</div>
                </div>
                <div className="bg-white rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-amber-600">
                    {(deltaMetrics.sync_time || 0).toFixed(3)}s
                  </div>
                  <div className="text-sm text-gray-600">Sync Time</div>
                </div>
              </div>
            </motion.div>
          )}

          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium text-gray-700">Editing as node:</label>
                <select
                  value={activeNode}
                  onChange={(e) => setActiveNode(e.target.value)}
                  className="text-sm border border-gray-300 rounded-md px-3 py-1"
                >
                  {nodes.map(node => (
                    <option key={node.node_id} value={node.node_id}>
                      {node.name}
                    </option>
                  ))}
                </select>
              </div>
              
              {lastSyncTime && (
                <div className="flex items-center space-x-1 text-sm text-gray-500">
                  <Clock className="w-4 h-4" />
                  <span>Last sync: {lastSyncTime.toLocaleTimeString()}</span>
                </div>
              )}
            </div>

            <button
              onClick={saveFile}
              disabled={isSaving || fileContent === originalContent}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 flex items-center space-x-2"
            >
              {isSaving ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>Save & Sync to All Nodes</span>
            </button>
          </div>

          <div className="flex-1 border border-gray-300 rounded-lg overflow-hidden">
            {isLoading ? (
              <div className="h-full flex items-center justify-center">
                <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
              </div>
            ) : (
              <textarea
                value={fileContent}
                onChange={(e) => setFileContent(e.target.value)}
                className="w-full h-full p-4 font-mono text-sm border-none resize-none focus:outline-none"
                placeholder="File content will appear here..."
              />
            )}
          </div>
        </div>

        <div className="border-t border-gray-200 p-4 bg-gray-50">
          <div className="text-sm text-gray-600 flex items-center justify-between">
            <span>💡 Edit content and save to see delta synchronization across all connected nodes</span>
            <span>File size: {formatBytes(new TextEncoder().encode(fileContent).length)}</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default MultiNodeEditor; 