import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Node management
export const nodeApi = {
  register: async (nodeData) => {
    const response = await api.post('/api/register', nodeData);
    return response.data;
  },

  getAll: async () => {
    const response = await api.get('/api/nodes');
    return response.data;
  },

  getById: async (nodeId) => {
    const response = await api.get(`/api/nodes/${nodeId}`);
    return response.data;
  },

  getFiles: async (nodeId) => {
    const response = await api.get(`/api/nodes/${nodeId}/files`);
    return response.data;
  },

  remove: async (nodeId) => {
    const response = await api.delete(`/api/nodes/${nodeId}`);
    return response.data;
  },
};

// File management
export const fileApi = {
  getAll: async () => {
    const response = await api.get('/api/files');
    return response.data;
  },

  getById: async (fileId) => {
    const response = await api.get(`/api/files/${fileId}`);
    return response.data;
  },

  getChunks: async (fileId) => {
    const response = await api.get(`/api/files/${fileId}/chunks`);
    return response.data;
  },

  upload: async (fileData, progressCallback) => {
    const formData = new FormData();
    
    // Create file metadata
    const metadata = {
      file_id: `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: fileData.name,
      path: `/${fileData.selectedNode}/${fileData.name}`,
      size: fileData.file.size,
      hash: '', // Will be calculated on backend
      created_at: new Date().toISOString(),
      modified_at: new Date().toISOString(),
      owner_node: fileData.selectedNode,
      version: 1,
      vector_clock: { clocks: {} },
      is_deleted: false,
      content_type: fileData.file.type || 'application/octet-stream'
    };

    // Create chunks from file
    const chunks = await createFileChunks(fileData.file);
    
    const requestData = {
      file_metadata: metadata,
      chunks: chunks,
      vector_clock: { clocks: { [fileData.selectedNode]: 1 } },
      use_delta_sync: true
    };

    const response = await api.post('/api/files/upload', requestData, {
      onUploadProgress: (progressEvent) => {
        if (progressCallback) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          progressCallback(percentCompleted);
        }
      },
    });

    return response.data;
  },

  getHistory: async (fileId) => {
    const response = await api.get(`/api/files/${fileId}/history`);
    return response.data;
  },

  delete: async (fileId, nodeId) => {
    const response = await api.delete(`/api/files/${fileId}`, {
      data: { node_id: nodeId }
    });
    return response.data;
  },

  getByNode: async (nodeId) => {
    const response = await api.get(`/api/nodes/${nodeId}/files`);
    return response.data;
  }
};

// System metrics
export const metricsApi = {
  get: async () => {
    const response = await api.get('/api/metrics');
    return response.data;
  },
};

// Events
export const eventsApi = {
  getRecent: async (limit = 50) => {
    const response = await api.get(`/api/events?limit=${limit}`);
    return response.data;
  },
};

// Utility function to create file chunks
const createFileChunks = async (file) => {
  const CHUNK_SIZE = 4096;
  const chunks = [];
  
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    
    reader.onload = (event) => {
      const arrayBuffer = event.target.result;
      const uint8Array = new Uint8Array(arrayBuffer);
      
      for (let i = 0; i < uint8Array.length; i += CHUNK_SIZE) {
        const chunk = uint8Array.slice(i, i + CHUNK_SIZE);
        
        // Convert to base64 string for JSON serialization
        const base64Data = btoa(String.fromCharCode.apply(null, chunk));
        
        chunks.push({
          index: Math.floor(i / CHUNK_SIZE),
          offset: i,
          size: chunk.length,
          hash: '', // Will be calculated on backend
          data: base64Data // Send as base64 string instead of array
        });
      }
      
      resolve(chunks);
    };
    
    reader.onerror = () => {
      reject(new Error('Failed to read file'));
    };
    
    reader.readAsArrayBuffer(file);
  });
};

// Format file size
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// Format date
export const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString();
};

export default api; 