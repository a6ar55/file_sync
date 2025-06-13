import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line
} from 'recharts';
import { 
  TrendingUp, 
  TrendingDown, 
  HardDrive, 
  Zap, 
  Save,
  Clock,
  Layers,
  Package,
  FileText
} from 'lucide-react';

const DeltaSyncDashboard = () => {
  const [deltaMetrics, setDeltaMetrics] = useState({
    total_bandwidth_saved: 0,
    total_files_synced: 0,
    average_compression_ratio: 0,
    chunk_cache_size: 0,
    chunk_size: 4096
  });
  
  const [syncHistory, setSyncHistory] = useState([]);
  const [compressionStats, setCompressionStats] = useState([]);
  const [chunkingData, setChunkingData] = useState([]);

  // Fetch delta sync metrics
  useEffect(() => {
    const fetchDeltaMetrics = async () => {
      try {
        const response = await fetch('/api/delta-metrics');
        if (response.ok) {
          const data = await response.json();
          setDeltaMetrics(data);
        }
      } catch (error) {
        console.error('Failed to fetch delta metrics:', error);
      }
    };

    fetchDeltaMetrics();
    const interval = setInterval(fetchDeltaMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  // Generate sample data for charts (in real app, this would come from API)
  useEffect(() => {
    // Sync history data
    const now = new Date();
    const history = Array.from({ length: 24 }, (_, i) => {
      const time = new Date(now.getTime() - (23 - i) * 60 * 60 * 1000);
      return {
        time: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        bandwidthSaved: Math.floor(Math.random() * 500) + 100,
        filesSync: Math.floor(Math.random() * 10) + 1,
        efficiency: Math.floor(Math.random() * 40) + 60
      };
    });
    setSyncHistory(history);

    // Compression stats
    const compression = [
      { name: 'Unchanged Chunks', value: 65, color: '#10b981' },
      { name: 'Modified Chunks', value: 25, color: '#3b82f6' },
      { name: 'New Chunks', value: 10, color: '#f59e0b' }
    ];
    setCompressionStats(compression);

    // Chunking data
    const chunking = Array.from({ length: 12 }, (_, i) => ({
      fileSize: `${(i + 1) * 100}KB`,
      chunks: Math.floor((i + 1) * 100 / 4) + Math.floor(Math.random() * 10),
      reused: Math.floor(((i + 1) * 100 / 4) * 0.7) + Math.floor(Math.random() * 5),
      transferred: Math.floor(((i + 1) * 100 / 4) * 0.3) + Math.floor(Math.random() * 5)
    }));
    setChunkingData(chunking);
  }, []);

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const efficiency = deltaMetrics.average_compression_ratio || 0;
  const bandwidthSaved = deltaMetrics.total_bandwidth_saved || 0;

  const renderDeltaSyncIndicator = (file) => {
    if (!file.delta_sync_info) return null;
    
    const { bytes_saved, total_bytes } = file.delta_sync_info;
    const savings_percentage = ((bytes_saved / total_bytes) * 100).toFixed(1);
    
    return (
      <div className="flex items-center space-x-2 text-sm">
        <div className="flex items-center space-x-1 text-green-600">
          <HardDrive className="w-4 h-4" />
          <span>{savings_percentage}% saved</span>
        </div>
        <div className="text-gray-500">
          ({formatBytes(bytes_saved)} of {formatBytes(total_bytes)})
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Delta Synchronization Performance</h2>
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center space-x-2">
            <Package className="w-4 h-4 text-blue-500" />
            <span className="text-gray-600">{deltaMetrics.chunk_size}B chunks</span>
          </div>
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-500" />
            <span className="text-gray-600">{deltaMetrics.chunk_cache_size} cached</span>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-gradient-to-r from-green-500 to-green-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm">Bandwidth Saved</p>
              <p className="text-2xl font-bold">{formatBytes(bandwidthSaved)}</p>
            </div>
            <TrendingDown className="w-8 h-8 text-green-200" />
          </div>
          <div className="mt-2 flex items-center text-green-100 text-xs">
            <TrendingUp className="w-3 h-3 mr-1" />
            <span>+12% from last hour</span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm">Files Synchronized</p>
              <p className="text-2xl font-bold">{deltaMetrics.total_files_synced}</p>
            </div>
            <Zap className="w-8 h-8 text-blue-200" />
          </div>
          <div className="mt-2 flex items-center text-blue-100 text-xs">
            <Clock className="w-3 h-3 mr-1" />
            <span>24 files today</span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm">Efficiency</p>
              <p className="text-2xl font-bold">{efficiency.toFixed(1)}%</p>
            </div>
            <HardDrive className="w-8 h-8 text-purple-200" />
          </div>
          <div className="mt-2 flex items-center text-purple-100 text-xs">
            <Save className="w-3 h-3 mr-1" />
            <span>Avg compression ratio</span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-gradient-to-r from-yellow-500 to-yellow-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-yellow-100 text-sm">Cache Size</p>
              <p className="text-2xl font-bold">{deltaMetrics.chunk_cache_size}</p>
            </div>
            <Layers className="w-8 h-8 text-yellow-200" />
          </div>
          <div className="mt-2 flex items-center text-yellow-100 text-xs">
            <Package className="w-3 h-3 mr-1" />
            <span>Cached chunks</span>
          </div>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bandwidth Usage Chart */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-gray-50 rounded-lg p-4"
        >
          <h3 className="text-lg font-medium text-gray-900 mb-4">Bandwidth Usage (24 Hours)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={syncHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="time" 
                stroke="#6b7280"
                fontSize={12}
                interval="preserveStartEnd"
              />
              <YAxis stroke="#6b7280" fontSize={12} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#f9fafb', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px'
                }}
              />
              <Line 
                type="monotone" 
                dataKey="bandwidthSaved" 
                stroke="#10b981" 
                strokeWidth={2}
                dot={{ r: 4 }}
                name="Bandwidth Saved (KB)"
              />
            </LineChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Compression Ratio Pie Chart */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
          className="bg-gray-50 rounded-lg p-4"
        >
          <h3 className="text-lg font-medium text-gray-900 mb-4">Chunk Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={compressionStats}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={5}
                dataKey="value"
              >
                {compressionStats.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip 
                formatter={(value) => `${value}%`}
                contentStyle={{ 
                  backgroundColor: '#f9fafb', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px'
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center space-x-4 mt-4">
            {compressionStats.map((stat) => (
              <div key={stat.name} className="flex items-center space-x-2">
                <div 
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: stat.color }}
                ></div>
                <span className="text-xs text-gray-600">{stat.name}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Sync Efficiency Over Time */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="bg-gray-50 rounded-lg p-4"
        >
          <h3 className="text-lg font-medium text-gray-900 mb-4">Sync Efficiency</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={syncHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="time" 
                stroke="#6b7280"
                fontSize={12}
                interval="preserveStartEnd"
              />
              <YAxis stroke="#6b7280" fontSize={12} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#f9fafb', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px'
                }}
              />
              <Bar 
                dataKey="efficiency" 
                fill="#3b82f6"
                radius={[2, 2, 0, 0]}
                name="Efficiency (%)"
              />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Chunking Analysis */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="bg-gray-50 rounded-lg p-4"
        >
          <h3 className="text-lg font-medium text-gray-900 mb-4">Chunk Reuse by File Size</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chunkingData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="fileSize" 
                stroke="#6b7280"
                fontSize={12}
              />
              <YAxis stroke="#6b7280" fontSize={12} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#f9fafb', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px'
                }}
              />
              <Bar 
                dataKey="reused" 
                stackId="chunks"
                fill="#10b981"
                name="Reused Chunks"
                radius={[0, 0, 0, 0]}
              />
              <Bar 
                dataKey="transferred" 
                stackId="chunks"
                fill="#f59e0b"
                name="Transferred Chunks"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Performance Summary */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.9 }}
        className="mt-6 bg-blue-50 rounded-lg p-4 border border-blue-200"
      >
        <h3 className="text-lg font-medium text-blue-900 mb-3">Performance Summary</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="text-blue-800">
            <strong>Bandwidth Efficiency:</strong>
            <br />
            Delta sync saved {formatBytes(bandwidthSaved)} of bandwidth through chunk reuse, 
            achieving an average compression ratio of {efficiency.toFixed(1)}%.
          </div>
          <div className="text-blue-800">
            <strong>Chunk Management:</strong>
            <br />
            {deltaMetrics.chunk_cache_size} chunks cached with {deltaMetrics.chunk_size}B size. 
            Approximately 70% of chunks are reused across synchronizations.
          </div>
          <div className="text-blue-800">
            <strong>Sync Performance:</strong>
            <br />
            {deltaMetrics.total_files_synced} files synchronized successfully. 
            Rolling hash optimization reduces transfer time by identifying unchanged blocks.
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default DeltaSyncDashboard; 