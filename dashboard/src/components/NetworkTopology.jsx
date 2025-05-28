import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Server, 
  Wifi, 
  WifiOff, 
  Activity, 
  Zap,
  RefreshCw,
  Circle
} from 'lucide-react';

const NetworkTopology = ({ nodes = [], syncEvents = [] }) => {
  const [topology, setTopology] = useState(null);
  const [activeDataFlows, setActiveDataFlows] = useState([]);
  const [networkStats, setNetworkStats] = useState({
    totalNodes: 0,
    onlineNodes: 0,
    avgLatency: 0,
    totalConnections: 0
  });

  // Fetch network topology data
  useEffect(() => {
    const fetchTopology = async () => {
      try {
        const response = await fetch('/api/network-topology');
        if (response.ok) {
          const data = await response.json();
          setTopology(data);
          
          // Update network stats
          const onlineNodes = data.nodes.filter(n => n.status === 'online');
          const avgLatency = data.connections.reduce((sum, conn) => sum + conn.latency, 0) / data.connections.length;
          
          setNetworkStats({
            totalNodes: data.nodes.length,
            onlineNodes: onlineNodes.length,
            avgLatency: avgLatency || 0,
            totalConnections: data.connections.length
          });
        }
      } catch (error) {
        console.error('Failed to fetch network topology:', error);
      }
    };

    fetchTopology();
    const interval = setInterval(fetchTopology, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  // Process sync events for data flow visualization
  useEffect(() => {
    if (!syncEvents || syncEvents.length === 0) return;

    const dataFlows = [];
    syncEvents.forEach(event => {
      if (event.event_type === 'file_sync_progress' && event.data.action === 'syncing') {
        dataFlows.push({
          id: `${event.data.source_node}-${event.data.target_node}-${Date.now()}`,
          from: event.data.source_node,
          to: event.data.target_node,
          fileName: event.data.file_name,
          progress: event.data.progress,
          timestamp: Date.now()
        });
      }
    });

    setActiveDataFlows(prev => {
      const now = Date.now();
      // Remove old data flows (older than 10 seconds)
      const filtered = prev.filter(flow => now - flow.timestamp < 10000);
      return [...filtered, ...dataFlows];
    });
  }, [syncEvents]);

  const getNodeColor = (status) => {
    switch (status) {
      case 'online': return '#10b981'; // green
      case 'syncing': return '#3b82f6'; // blue
      case 'offline': return '#6b7280'; // gray
      default: return '#6b7280';
    }
  };

  const getConnectionColor = (status, latency) => {
    if (status === 'inactive') return '#6b7280';
    if (latency > 100) return '#ef4444'; // red for high latency
    if (latency > 50) return '#f59e0b'; // yellow for medium latency
    return '#10b981'; // green for low latency
  };

  if (!topology) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
          <span className="ml-2 text-gray-600">Loading network topology...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Network Topology</h2>
        <div className="flex items-center space-x-6 text-sm">
          <div className="flex items-center space-x-2">
            <Circle className="w-3 h-3 text-green-500 fill-current" />
            <span className="text-gray-600">Online ({networkStats.onlineNodes})</span>
          </div>
          <div className="flex items-center space-x-2">
            <Circle className="w-3 h-3 text-gray-400 fill-current" />
            <span className="text-gray-600">Total ({networkStats.totalNodes})</span>
          </div>
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-blue-500" />
            <span className="text-gray-600">{networkStats.avgLatency.toFixed(1)}ms avg</span>
          </div>
        </div>
      </div>

      <div className="relative bg-gray-50 rounded-lg p-4 h-96 overflow-hidden">
        <svg width="100%" height="100%" viewBox="0 0 600 400" className="absolute inset-0">
          {/* Background grid */}
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e5e7eb" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Connections */}
          {topology.connections.map((connection, index) => {
            const fromNode = connection.from === 'coordinator' 
              ? topology.coordinator 
              : topology.nodes.find(n => n.id === connection.from);
            const toNode = connection.to === 'coordinator' 
              ? topology.coordinator 
              : topology.nodes.find(n => n.id === connection.to);

            if (!fromNode || !toNode) return null;

            return (
              <g key={`connection-${index}`}>
                {/* Connection line */}
                <motion.line
                  x1={fromNode.x}
                  y1={fromNode.y}
                  x2={toNode.x}
                  y2={toNode.y}
                  stroke={getConnectionColor(connection.status, connection.latency)}
                  strokeWidth="2"
                  strokeDasharray={connection.status === 'active' ? "none" : "5,5"}
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: 1, delay: index * 0.1 }}
                />

                {/* Latency label */}
                {connection.status === 'active' && (
                  <motion.g
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 1 + index * 0.1 }}
                  >
                    <rect
                      x={(fromNode.x + toNode.x) / 2 - 15}
                      y={(fromNode.y + toNode.y) / 2 - 8}
                      width="30"
                      height="16"
                      rx="8"
                      fill="rgba(0,0,0,0.7)"
                    />
                    <text
                      x={(fromNode.x + toNode.x) / 2}
                      y={(fromNode.y + toNode.y) / 2 + 4}
                      textAnchor="middle"
                      className="text-xs font-medium fill-white"
                    >
                      {connection.latency}ms
                    </text>
                  </motion.g>
                )}
              </g>
            );
          })}

          {/* Data flow animations */}
          <AnimatePresence>
            {activeDataFlows.map((flow) => {
              const fromNode = topology.nodes.find(n => n.id === flow.from);
              const toNode = topology.nodes.find(n => n.id === flow.to);
              
              if (!fromNode || !toNode) return null;

              return (
                <motion.g key={flow.id}>
                  {/* Data packet */}
                  <motion.circle
                    cx={fromNode.x}
                    cy={fromNode.y}
                    r="4"
                    fill="#3b82f6"
                    initial={{ cx: fromNode.x, cy: fromNode.y, opacity: 0 }}
                    animate={{ 
                      cx: toNode.x, 
                      cy: toNode.y, 
                      opacity: [0, 1, 1, 0] 
                    }}
                    exit={{ opacity: 0 }}
                    transition={{ 
                      duration: 2, 
                      ease: "easeInOut",
                      opacity: { times: [0, 0.1, 0.9, 1] }
                    }}
                  />
                  
                  {/* Progress indicator */}
                  <motion.text
                    x={fromNode.x + (toNode.x - fromNode.x) * 0.5}
                    y={fromNode.y + (toNode.y - fromNode.y) * 0.5 - 10}
                    textAnchor="middle"
                    className="text-xs font-bold fill-blue-600"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: [0, 1, 1, 0] }}
                    transition={{ duration: 2, times: [0, 0.1, 0.9, 1] }}
                  >
                    {flow.progress}%
                  </motion.text>
                </motion.g>
              );
            })}
          </AnimatePresence>

          {/* Coordinator node */}
          <motion.g
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.5, delay: 0.5 }}
          >
            <circle
              cx={topology.coordinator.x}
              cy={topology.coordinator.y}
              r="30"
              fill="#1f2937"
              stroke="#60a5fa"
              strokeWidth="3"
              className="drop-shadow-lg"
            />
            <foreignObject
              x={topology.coordinator.x - 12}
              y={topology.coordinator.y - 12}
              width="24"
              height="24"
            >
              <Server className="w-6 h-6 text-white" />
            </foreignObject>
            <text
              x={topology.coordinator.x}
              y={topology.coordinator.y + 45}
              textAnchor="middle"
              className="text-sm font-bold text-gray-700"
            >
              Coordinator
            </text>
          </motion.g>

          {/* Client nodes */}
          {topology.nodes.map((node, index) => (
            <motion.g
              key={node.id}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5, delay: 1 + index * 0.2 }}
            >
              {/* Node circle */}
              <circle
                cx={node.x}
                cy={node.y}
                r="20"
                fill={getNodeColor(node.status)}
                stroke="#ffffff"
                strokeWidth="3"
                className="drop-shadow-md"
              />

              {/* Status indicator */}
              <motion.circle
                cx={node.x + 12}
                cy={node.y - 12}
                r="4"
                fill={node.status === 'online' ? '#10b981' : '#6b7280'}
                animate={{ 
                  scale: node.status === 'online' ? [1, 1.2, 1] : 1,
                  opacity: node.status === 'online' ? [1, 0.7, 1] : 0.5
                }}
                transition={{ 
                  duration: 2, 
                  repeat: node.status === 'online' ? Infinity : 0 
                }}
              />

              {/* Node icon */}
              <foreignObject
                x={node.x - 8}
                y={node.y - 8}
                width="16"
                height="16"
              >
                {node.status === 'online' ? (
                  <Wifi className="w-4 h-4 text-white" />
                ) : (
                  <WifiOff className="w-4 h-4 text-white" />
                )}
              </foreignObject>

              {/* File count badge */}
              {node.file_count > 0 && (
                <g>
                  <circle
                    cx={node.x - 12}
                    cy={node.y - 12}
                    r="8"
                    fill="#ef4444"
                    stroke="#ffffff"
                    strokeWidth="2"
                  />
                  <text
                    x={node.x - 12}
                    y={node.y - 8}
                    textAnchor="middle"
                    className="text-xs font-bold fill-white"
                  >
                    {node.file_count}
                  </text>
                </g>
              )}

              {/* Node label */}
              <text
                x={node.x}
                y={node.y + 35}
                textAnchor="middle"
                className="text-xs font-medium text-gray-700"
              >
                {node.name}
              </text>

              {/* Vector clock display */}
              <text
                x={node.x}
                y={node.y + 50}
                textAnchor="middle"
                className="text-xs text-gray-500"
              >
                {node.vector_clock}
              </text>
            </motion.g>
          ))}
        </svg>

        {/* Network activity indicator */}
        <div className="absolute top-4 right-4">
          <motion.div
            className="flex items-center space-x-2 bg-white px-3 py-1 rounded-full shadow-md"
            animate={{ 
              scale: activeDataFlows.length > 0 ? [1, 1.05, 1] : 1 
            }}
            transition={{ duration: 1, repeat: Infinity }}
          >
            <Zap className={`w-4 h-4 ${activeDataFlows.length > 0 ? 'text-blue-500' : 'text-gray-400'}`} />
            <span className="text-xs font-medium text-gray-700">
              {activeDataFlows.length} active transfers
            </span>
          </motion.div>
        </div>
      </div>

      {/* Network statistics */}
      <div className="mt-4 grid grid-cols-4 gap-4">
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-600">{networkStats.totalConnections}</div>
          <div className="text-sm text-blue-700">Connections</div>
        </div>
        <div className="bg-green-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-600">{networkStats.onlineNodes}</div>
          <div className="text-sm text-green-700">Online Nodes</div>
        </div>
        <div className="bg-yellow-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-yellow-600">{networkStats.avgLatency.toFixed(1)}ms</div>
          <div className="text-sm text-yellow-700">Avg Latency</div>
        </div>
        <div className="bg-purple-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-purple-600">{activeDataFlows.length}</div>
          <div className="text-sm text-purple-700">Data Flows</div>
        </div>
      </div>
    </div>
  );
};

export default NetworkTopology; 