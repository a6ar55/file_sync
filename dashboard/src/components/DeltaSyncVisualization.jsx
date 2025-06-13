import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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
  Line,
  Area,
  AreaChart
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
  FileText,
  Download,
  Upload,
  Wifi,
  Activity,
  Edit,
  Plus
} from 'lucide-react';

const DeltaSyncVisualization = () => {
  const [syncEvents, setSyncEvents] = useState([]);
  const [chunkData, setChunkData] = useState([]);
  const [networkStats, setNetworkStats] = useState({
    totalTransmitted: 0,
    totalSaved: 0,
    efficiency: 0
  });
  const [realtimeActivity, setRealtimeActivity] = useState([]);

  // Fetch sync events and delta metrics
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Get recent sync events
        const eventsResponse = await fetch('/api/events?limit=50');
        if (eventsResponse.ok) {
          const events = await eventsResponse.json();
          const syncEvents = events.filter(e => 
            e.event_type === 'file_modified' || 
            e.event_type === 'sync_completed'
          ).slice(0, 10);
          setSyncEvents(syncEvents);
          
          // Process events for visualization
          processEventsForVisualization(syncEvents);
        }

        // Get delta metrics
        const deltaResponse = await fetch('/api/delta-metrics');
        if (deltaResponse.ok) {
          const deltaMetrics = await deltaResponse.json();
          updateNetworkStats(deltaMetrics);
        }
      } catch (error) {
        console.error('Failed to fetch delta sync data:', error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const processEventsForVisualization = (events) => {
    const chunkAnalysis = events.map((event, index) => {
      const data = event.data || {};
      const chunksTotal = data.chunks_total || 0;
      const chunksUnchanged = data.chunks_unchanged || 0;
      const chunksTransferred = data.chunks_transferred || 0;
      const bandwidthSaved = data.bandwidth_saved || 0;
      
      return {
        id: index,
        fileName: data.file_name || `File ${index + 1}`,
        timestamp: new Date(event.timestamp).toLocaleTimeString(),
        chunksTotal,
        chunksUnchanged,
        chunksTransferred,
        chunksNew: Math.max(0, chunksTransferred - (chunksTotal - chunksUnchanged)),
        efficiency: chunksTotal > 0 ? ((chunksUnchanged / chunksTotal) * 100) : 0,
        bandwidthSaved,
        compressionRatio: data.compression_ratio || 0
      };
    });

    setChunkData(chunkAnalysis);
    
    // Create realtime activity data
    const activity = events.slice(0, 6).map((event, index) => ({
      time: new Date(event.timestamp).toLocaleTimeString(),
      transmitted: (event.data?.file_size || 0) - (event.data?.bandwidth_saved || 0),
      saved: event.data?.bandwidth_saved || 0,
      efficiency: event.data?.compression_ratio || 0
    }));
    
    setRealtimeActivity(activity.reverse());
  };

  const updateNetworkStats = (deltaMetrics) => {
    setNetworkStats({
      totalTransmitted: 150000, // Mock data - in real app, calculate from events
      totalSaved: deltaMetrics.total_bandwidth_saved || 0,
      efficiency: deltaMetrics.average_compression_ratio || 0
    });
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const COLORS = {
    unchanged: '#10B981', // green
    modified: '#F59E0B',  // amber
    new: '#EF4444',       // red
    transmitted: '#3B82F6', // blue
    saved: '#10B981'      // green
  };

  const ChunkVisualization = ({ data }) => (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
      {/* Chunk Distribution */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Package className="w-5 h-5 mr-2 text-blue-600" />
          Chunk Distribution
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data.slice(-5)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="fileName" tick={{ fontSize: 12 }} />
            <YAxis />
            <Tooltip 
              formatter={(value, name) => [value, name]}
              labelFormatter={(label) => `File: ${label}`}
            />
            <Bar dataKey="chunksUnchanged" stackId="a" fill={COLORS.unchanged} name="Unchanged" />
            <Bar dataKey="chunksTransferred" stackId="a" fill={COLORS.modified} name="Modified" />
            <Bar dataKey="chunksNew" stackId="a" fill={COLORS.new} name="New" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Efficiency Over Time */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <TrendingUp className="w-5 h-5 mr-2 text-green-600" />
          Sync Efficiency
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.slice(-5)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 100]} />
            <Tooltip 
              formatter={(value) => [`${value.toFixed(1)}%`, 'Efficiency']}
            />
            <Line 
              type="monotone" 
              dataKey="efficiency" 
              stroke={COLORS.unchanged} 
              strokeWidth={3}
              dot={{ fill: COLORS.unchanged, strokeWidth: 2, r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );

  const NetworkTransmissionView = () => (
    <div className="bg-white rounded-lg shadow-md p-6 mb-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
        <Wifi className="w-5 h-5 mr-2 text-blue-600" />
        Network Transmission Analysis
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Bandwidth Usage */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-3">Bandwidth Usage Comparison</h4>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={[
                  { name: 'Data Transmitted', value: networkStats.totalTransmitted, fill: COLORS.transmitted },
                  { name: 'Bandwidth Saved', value: networkStats.totalSaved, fill: COLORS.saved }
                ]}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
              >
                {[].map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => formatBytes(value)} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Real-time Activity */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-3">Recent Activity</h4>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={realtimeActivity}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip formatter={(value) => formatBytes(value)} />
              <Area 
                type="monotone" 
                dataKey="transmitted" 
                stackId="1" 
                stroke={COLORS.transmitted} 
                fill={COLORS.transmitted} 
                fillOpacity={0.6}
                name="Transmitted"
              />
              <Area 
                type="monotone" 
                dataKey="saved" 
                stackId="1" 
                stroke={COLORS.saved} 
                fill={COLORS.saved} 
                fillOpacity={0.6}
                name="Saved"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );

  const FileEditingDemo = () => {
    const [demoStep, setDemoStep] = useState(0);
    const [isRunning, setIsRunning] = useState(false);

    const demoSteps = [
      { 
        title: "Original File", 
        description: "Upload complete file", 
        icon: FileText,
        color: "bg-blue-500",
        efficiency: 0
      },
      { 
        title: "Small Edit", 
        description: "Modified 2 paragraphs", 
        icon: Edit,
        color: "bg-green-500",
        efficiency: 94
      },
      { 
        title: "Add Section", 
        description: "Added new content", 
        icon: Plus,
        color: "bg-amber-500",
        efficiency: 87
      },
      { 
        title: "Distributed Changes", 
        description: "Multiple small edits", 
        icon: Zap,
        color: "bg-purple-500",
        efficiency: 81
      }
    ];

    const runDemo = async () => {
      setIsRunning(true);
      for (let i = 0; i < demoSteps.length; i++) {
        setDemoStep(i);
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      setIsRunning(false);
    };

    return (
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-purple-600" />
            Delta Sync Demonstration
          </h3>
          <button
            onClick={runDemo}
            disabled={isRunning}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
          >
            {isRunning ? 'Running Demo...' : 'Run Demo'}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {demoSteps.map((step, index) => {
            const Icon = step.icon;
            const isActive = demoStep >= index;
            const isCurrent = demoStep === index && isRunning;

            return (
              <motion.div
                key={index}
                initial={{ opacity: 0.5, scale: 0.95 }}
                animate={{ 
                  opacity: isActive ? 1 : 0.5,
                  scale: isCurrent ? 1.05 : 1,
                  borderColor: isActive ? '#8B5CF6' : '#E5E7EB'
                }}
                className={`border-2 rounded-lg p-4 transition-all ${
                  isActive ? 'bg-purple-50' : 'bg-gray-50'
                }`}
              >
                <div className={`w-10 h-10 rounded-full ${step.color} flex items-center justify-center mb-3`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <h4 className="font-medium text-gray-900 mb-1">{step.title}</h4>
                <p className="text-sm text-gray-600 mb-2">{step.description}</p>
                {isActive && step.efficiency > 0 && (
                  <div className="text-sm font-medium text-green-600">
                    {step.efficiency}% efficient
                  </div>
                )}
                {isCurrent && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    className="w-4 h-4 border-2 border-purple-600 border-t-transparent rounded-full mt-2"
                  />
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg p-6 text-white">
        <h2 className="text-2xl font-bold mb-2">Delta Synchronization</h2>
        <p className="text-purple-100">
          Visualizing efficient file synchronization - only changes are transmitted over the network
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-r from-green-500 to-green-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm">Bandwidth Saved</p>
              <p className="text-2xl font-bold">{formatBytes(networkStats.totalSaved)}</p>
            </div>
            <TrendingDown className="w-8 h-8 text-green-200" />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm">Data Transmitted</p>
              <p className="text-2xl font-bold">{formatBytes(networkStats.totalTransmitted)}</p>
            </div>
            <Upload className="w-8 h-8 text-blue-200" />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm">Sync Efficiency</p>
              <p className="text-2xl font-bold">{networkStats.efficiency.toFixed(1)}%</p>
            </div>
            <Zap className="w-8 h-8 text-purple-200" />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-gradient-to-r from-amber-500 to-amber-600 rounded-lg p-4 text-white"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-amber-100 text-sm">Files Synced</p>
              <p className="text-2xl font-bold">{chunkData.length}</p>
            </div>
            <FileText className="w-8 h-8 text-amber-200" />
          </div>
        </motion.div>
      </div>

      {/* Interactive Demo */}
      <FileEditingDemo />

      {/* Network Transmission Analysis */}
      <NetworkTransmissionView />

      {/* Chunk-level Visualization */}
      <ChunkVisualization data={chunkData} />

      {/* Recent Sync Events */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Clock className="w-5 h-5 mr-2 text-gray-600" />
          Recent Sync Events
        </h3>
        <div className="space-y-3">
          <AnimatePresence>
            {syncEvents.slice(0, 5).map((event, index) => (
              <motion.div
                key={event.event_id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <div>
                    <p className="font-medium text-gray-900">
                      {event.data?.file_name || 'Unknown File'}
                    </p>
                    <p className="text-sm text-gray-600">
                      {new Date(event.timestamp).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-green-600">
                    {formatBytes(event.data?.bandwidth_saved || 0)} saved
                  </p>
                  <p className="text-xs text-gray-500">
                    {(event.data?.compression_ratio || 0).toFixed(1)}% efficiency
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default DeltaSyncVisualization; 