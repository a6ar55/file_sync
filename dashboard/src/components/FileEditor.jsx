import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Edit3, 
  Save, 
  Upload, 
  Download, 
  FileText, 
  Clock, 
  Activity,
  Zap,
  TrendingUp,
  RefreshCw,
  Eye,
  EyeOff,
  BarChart3
} from 'lucide-react';

const FileEditor = () => {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [deltaMetrics, setDeltaMetrics] = useState(null);
  const [showMetrics, setShowMetrics] = useState(true);
  const [lastSyncTime, setLastSyncTime] = useState(null);

  // Demo templates for creating new files
  const demoTemplates = {
    document: `# Document Template

## Introduction
This is a sample document to demonstrate delta synchronization.
You can edit this content and see how only the changed parts are transmitted.

## Section 1: Overview
Delta sync is a technique for efficient file synchronization.
It identifies and transmits only the changed chunks of a file.

## Section 2: Benefits
- Reduced bandwidth usage
- Faster synchronization
- Lower network overhead
- Perfect for collaborative editing

## Conclusion
Try editing different sections and watch the delta sync efficiency!`,

    code: `// JavaScript Code Template
function deltaSyncDemo() {
    // This is a code example to show delta sync with code files
    console.log("Welcome to delta sync demonstration");
    
    const features = [
        "Chunk-based synchronization",
        "Rolling hash algorithm", 
        "Bandwidth optimization",
        "Real-time collaboration"
    ];
    
    features.forEach(feature => {
        console.log(\`✓ \${feature}\`);
    });
    
    return {
        status: "active",
        efficiency: "high",
        bandwidthSaved: "85%"
    };
}

// Try modifying this function and see the delta sync in action!
deltaSyncDemo();`,

    config: `# Configuration File Template
# Edit these settings to see delta sync efficiency

[database]
host = localhost
port = 5432
name = filesync_db
user = admin

[synchronization]
chunk_size = 4096
compression = true
delta_sync = enabled
rollback_limit = 10

[performance]
max_connections = 100
timeout = 30
cache_size = 256MB
batch_size = 50

[logging]
level = info
file = /var/log/filesync.log
rotate = daily
max_size = 100MB`
  };

  useEffect(() => {
    fetchFiles();
  }, []);

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

  const createNewFile = async (template) => {
    const fileName = `demo_${template}_${Date.now()}.${template === 'code' ? 'js' : 'txt'}`;
    const content = demoTemplates[template];
    
    try {
      setIsLoading(true);
      
      // Create file metadata
      const fileMetadata = {
        file_id: `file_${Date.now()}`,
        name: fileName,
        path: `/demo/${fileName}`,
        size: content.length,
        hash: '', // Will be calculated by server
        created_at: new Date().toISOString(),
        modified_at: new Date().toISOString(),
        owner_node: 'file_editor',
        is_deleted: false,
        content_type: template === 'code' ? 'text/javascript' : 'text/plain'
      };

      // Convert content to chunks
      const chunks = createChunks(content);
      
      const response = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_metadata: fileMetadata,
          chunks: chunks,
          vector_clock: { clocks: { file_editor: 1 } },
          use_delta_sync: false
        })
      });

      if (response.ok) {
        const result = await response.json();
        await fetchFiles();
        setSelectedFile({ ...fileMetadata, version_id: result.version_id });
        setFileContent(content);
        setOriginalContent(content);
        setIsEditing(true);
      }
    } catch (error) {
      console.error('Failed to create file:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadFile = async (file) => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/files/${file.file_id}/content`);
      
      if (response.ok) {
        const data = await response.json();
        const content = hexToString(data.content);
        setSelectedFile(file);
        setFileContent(content);
        setOriginalContent(content);
        setIsEditing(false);
        setDeltaMetrics(null);
      }
    } catch (error) {
      console.error('Failed to load file:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const saveFile = async () => {
    if (!selectedFile || fileContent === originalContent) return;
    
    try {
      setIsLoading(true);
      const startTime = Date.now();
      
      // Calculate changes for preview
      const changes = calculateChanges(originalContent, fileContent);
      
      // Create chunks for upload
      const chunks = createChunks(fileContent);
      
      const fileMetadata = {
        ...selectedFile,
        size: fileContent.length,
        modified_at: new Date().toISOString()
      };

      const response = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_metadata: fileMetadata,
          chunks: chunks,
          vector_clock: { clocks: { file_editor: Date.now() } },
          use_delta_sync: true
        })
      });

      if (response.ok) {
        const result = await response.json();
        const syncTime = Date.now() - startTime;
        
        setDeltaMetrics({
          ...result.delta_metrics,
          sync_time: syncTime / 1000,
          changes_preview: changes
        });
        
        setOriginalContent(fileContent);
        setLastSyncTime(new Date());
        setIsEditing(false);
        
        // Refresh file list
        await fetchFiles();
      }
    } catch (error) {
      console.error('Failed to save file:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const createChunks = (content) => {
    const chunks = [];
    const chunkSize = 1024; // 1KB chunks for better demo
    const bytes = new TextEncoder().encode(content);
    
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.slice(i, Math.min(i + chunkSize, bytes.length));
      chunks.push({
        index: chunks.length,
        offset: i,
        size: chunk.length,
        hash: '', // Server will calculate
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

  const calculateChanges = (oldText, newText) => {
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    
    const changes = {
      added: 0,
      modified: 0,
      unchanged: 0,
      total: newLines.length
    };
    
    const maxLines = Math.max(oldLines.length, newLines.length);
    
    for (let i = 0; i < maxLines; i++) {
      const oldLine = oldLines[i] || '';
      const newLine = newLines[i] || '';
      
      if (oldLine === newLine) {
        changes.unchanged++;
      } else if (oldLines[i] === undefined) {
        changes.added++;
      } else {
        changes.modified++;
      }
    }
    
    return changes;
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const DeltaMetricsCard = ({ metrics }) => (
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
        <span className="text-sm text-green-600">
          {lastSyncTime?.toLocaleTimeString()}
        </span>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-600">
            {metrics.compression_ratio?.toFixed(1) || 0}%
          </div>
          <div className="text-sm text-gray-600">Efficiency</div>
        </div>
        
        <div className="bg-white rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-600">
            {formatBytes(metrics.bandwidth_saved || 0)}
          </div>
          <div className="text-sm text-gray-600">Saved</div>
        </div>
        
        <div className="bg-white rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-purple-600">
            {metrics.chunks_unchanged || 0}
          </div>
          <div className="text-sm text-gray-600">Reused Chunks</div>
        </div>
        
        <div className="bg-white rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-amber-600">
            {(metrics.sync_time || 0).toFixed(3)}s
          </div>
          <div className="text-sm text-gray-600">Sync Time</div>
        </div>
      </div>

      {metrics.changes_preview && (
        <div className="mt-4 p-3 bg-white rounded-lg">
          <h4 className="font-medium text-gray-800 mb-2">Content Analysis:</h4>
          <div className="flex space-x-4 text-sm">
            <span className="text-green-600">
              ✓ {metrics.changes_preview.unchanged} unchanged lines
            </span>
            <span className="text-amber-600">
              ⚡ {metrics.changes_preview.modified} modified lines
            </span>
            <span className="text-blue-600">
              + {metrics.changes_preview.added} added lines
            </span>
          </div>
        </div>
      )}
    </motion.div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-6 text-white">
        <h2 className="text-2xl font-bold mb-2 flex items-center">
          <Edit3 className="w-6 h-6 mr-3" />
          Interactive File Editor
        </h2>
        <p className="text-blue-100">
          Edit files in real-time and watch delta synchronization in action
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* File List */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Files</h3>
            <button
              onClick={fetchFiles}
              className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {/* Create New File */}
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Create Demo File:</h4>
            <div className="space-y-2">
              {Object.keys(demoTemplates).map(template => (
                <button
                  key={template}
                  onClick={() => createNewFile(template)}
                  disabled={isLoading}
                  className="w-full px-3 py-2 text-sm bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors disabled:opacity-50"
                >
                  {template.charAt(0).toUpperCase() + template.slice(1)} Template
                </button>
              ))}
            </div>
          </div>

          {/* Existing Files */}
          <div className="space-y-2">
            {files.map((file) => (
              <motion.div
                key={file.file_id}
                whileHover={{ scale: 1.02 }}
                onClick={() => loadFile(file)}
                className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                  selectedFile?.file_id === file.file_id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <FileText className="w-4 h-4 text-gray-500" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatBytes(file.size)}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Editor */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-md">
          <div className="border-b border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <h3 className="text-lg font-semibold text-gray-900">
                  {selectedFile ? selectedFile.name : 'Select a file to edit'}
                </h3>
                {deltaMetrics && (
                  <button
                    onClick={() => setShowMetrics(!showMetrics)}
                    className="p-1 text-gray-500 hover:text-gray-700"
                  >
                    {showMetrics ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                )}
              </div>
              
              {selectedFile && (
                <div className="flex space-x-2">
                  <button
                    onClick={() => setIsEditing(!isEditing)}
                    className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
                  >
                    {isEditing ? 'View' : 'Edit'}
                  </button>
                  
                  {isEditing && fileContent !== originalContent && (
                    <button
                      onClick={saveFile}
                      disabled={isLoading}
                      className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 flex items-center space-x-1"
                    >
                      <Save className="w-3 h-3" />
                      <span>Save & Sync</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="p-4">
            {/* Delta Metrics */}
            <AnimatePresence>
              {deltaMetrics && showMetrics && (
                <DeltaMetricsCard metrics={deltaMetrics} />
              )}
            </AnimatePresence>

            {/* Content Editor */}
            {selectedFile ? (
              <div className="space-y-4">
                <textarea
                  value={fileContent}
                  onChange={(e) => setFileContent(e.target.value)}
                  readOnly={!isEditing}
                  className={`w-full h-96 p-4 border rounded-lg font-mono text-sm ${
                    isEditing 
                      ? 'border-blue-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500' 
                      : 'border-gray-200 bg-gray-50'
                  } resize-none focus:outline-none`}
                  placeholder="File content will appear here..."
                />
                
                {isEditing && (
                  <div className="text-sm text-gray-600">
                    💡 Tip: Make changes and click "Save & Sync" to see delta synchronization in action.
                    The system will show you exactly how much bandwidth was saved!
                  </div>
                )}
              </div>
            ) : (
              <div className="h-96 flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p className="text-lg">Select a file to view or edit</p>
                  <p className="text-sm">Create a demo file to see delta sync in action</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Info Panel */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-medium text-blue-900 mb-2 flex items-center">
          <Activity className="w-4 h-4 mr-2" />
          How Delta Sync Works
        </h4>
        <div className="text-sm text-blue-800 space-y-1">
          <p>• Files are divided into 1KB chunks, each with a unique signature</p>
          <p>• When you edit, only modified chunks are transmitted over the network</p>
          <p>• Unchanged chunks are reused from cache, saving bandwidth</p>
          <p>• The green metrics card shows real-time efficiency measurements</p>
        </div>
      </div>
    </div>
  );
};

export default FileEditor; 