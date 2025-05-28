import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Server, 
  RefreshCw, 
  ArrowRight,
  CheckCircle,
  AlertCircle,
  FileText,
  Users,
  Activity,
  Zap
} from 'lucide-react';

const SyncVisualization = ({ nodes, syncEvents, files }) => {
  const [activeSyncs, setActiveSyncs] = useState(new Map());
  const [recentActivity, setRecentActivity] = useState([]);

  // Process sync events to track active synchronizations
  useEffect(() => {
    if (!syncEvents || syncEvents.length === 0) return;

    const newActiveSyncs = new Map();
    const newActivity = [...recentActivity];

    // Process only the latest events
    const latestEvents = syncEvents.slice(-50);
    
    latestEvents.forEach((event, index) => {
      if (!event?.event_id || !event?.data) return;

      // Generate unique key using event_id and timestamp
      const uniqueKey = `${event.event_id}-${new Date(event.timestamp).getTime()}`;
      
      // Handle FILE_SYNC_PROGRESS events (using correct enum value)
      if (event.event_type === 'file_sync_progress') {
        const syncKey = `${event.data.file_id}-${event.data.source_node}-${event.data.target_node}`;
        
        // Check if this is a progress update
        if (event.data.action === 'sync_started' || event.data.action === 'syncing') {
          const existingSync = newActiveSyncs.get(syncKey);
          
          newActiveSyncs.set(syncKey, {
            id: syncKey,
            uniqueKey: existingSync?.uniqueKey || uniqueKey, // Keep original key for stability
            fileId: event.data.file_id,
            fileName: event.data.file_name || 'Unknown File',
            sourceNode: event.data.source_node,
            targetNode: event.data.target_node,
            progress: event.data.progress || 0,
            status: event.data.progress === 100 ? 'completed' : 'syncing',
            startTime: existingSync?.startTime || event.timestamp,
            lastUpdate: event.timestamp,
            action: event.data.action
          });
          
          // If this is the start, add to activity
          if (event.data.action === 'sync_started') {
            newActivity.unshift({
              id: uniqueKey,
              type: 'sync_started',
              fileName: event.data.file_name || 'Unknown File',
              sourceNode: event.data.source_node,
              targetNode: event.data.target_node,
              timestamp: new Date(event.timestamp)
            });
          }
        }
      }
      
      // Handle SYNC_COMPLETED events (using correct enum value)
      if (event.event_type === 'sync_completed') {
        const syncKey = `${event.data.file_id}-${event.data.source_node}-${event.data.target_node}`;
        
        // Remove from active syncs
        newActiveSyncs.delete(syncKey);
        
        // Add to recent activity with unique key
        newActivity.unshift({
          id: uniqueKey,
          type: 'sync_completed',
          fileName: event.data.file_name || 'Unknown File',
          sourceNode: event.data.source_node,
          targetNode: event.data.target_node,
          bytesTransferred: event.data.bytes_transferred,
          timestamp: new Date(event.timestamp)
        });
      }
      
      // Handle FILE_MODIFIED events for uploads
      if (event.event_type === 'file_modified' && event.data.action === 'uploaded') {
        newActivity.unshift({
          id: uniqueKey,
          type: 'file_uploaded',
          fileName: event.data.file_name || 'Unknown File',
          sourceNode: event.node_id,
          fileSize: event.data.file_size,
          timestamp: new Date(event.timestamp)
        });
      }

      // Handle SYNC_ERROR events
      if (event.event_type === 'sync_error') {
        const syncKey = `${event.data.file_id}-${event.data.source_node}-${event.data.target_node}`;
        
        // Remove from active syncs
        newActiveSyncs.delete(syncKey);
        
        // Add error to activity
        newActivity.unshift({
          id: uniqueKey,
          type: 'sync_error',
          fileName: event.data.file_name || 'Unknown File',
          sourceNode: event.data.source_node,
          targetNode: event.data.target_node,
          error: event.data.error,
          timestamp: new Date(event.timestamp)
        });
      }
    });

    // Clean up completed syncs older than 30 seconds
    const now = new Date();
    for (const [key, sync] of newActiveSyncs.entries()) {
      const timeDiff = (now - new Date(sync.lastUpdate)) / 1000;
      if (sync.progress === 100 && timeDiff > 30) {
        newActiveSyncs.delete(key);
      }
    }

    setActiveSyncs(newActiveSyncs);
    setRecentActivity(newActivity.slice(0, 25)); // Keep more activities for better tracking
  }, [syncEvents]);

  // Calculate network topology for visualization
  const networkTopology = useMemo(() => {
    const onlineNodes = nodes.filter(node => node.status === 'online');
    const radius = 150;
    const centerX = 200;
    const centerY = 200;
    
    return onlineNodes.map((node, index) => {
      const angle = (index * 2 * Math.PI) / onlineNodes.length;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      
      return {
        ...node,
        x,
        y,
        fileCount: files.filter(f => f.owner_node === node.node_id && !f.is_deleted).length
      };
    });
  }, [nodes, files]);

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getNodeColor = (node) => {
    if (node.status === 'online') return '#10b981'; // green
    if (node.status === 'syncing') return '#3b82f6'; // blue
    return '#6b7280'; // gray
  };

  const SyncConnection = ({ sync }) => {
    const sourceNode = networkTopology.find(n => n.node_id === sync.sourceNode);
    const targetNode = networkTopology.find(n => n.node_id === sync.targetNode);
    
    if (!sourceNode || !targetNode) return null;

    const progress = Math.max(0, Math.min(100, sync.progress || 0));
    const progressRatio = progress / 100;

    return (
      <g key={sync.uniqueKey}>
        {/* Connection line - background */}
        <line
          x1={sourceNode.x}
          y1={sourceNode.y}
          x2={targetNode.x}
          y2={targetNode.y}
          stroke="#e5e7eb"
          strokeWidth="4"
          strokeDasharray="none"
        />
        
        {/* Progress line overlay - shows actual transfer progress */}
        <motion.line
          x1={sourceNode.x}
          y1={sourceNode.y}
          x2={sourceNode.x + (targetNode.x - sourceNode.x) * progressRatio}
          y2={sourceNode.y + (targetNode.y - sourceNode.y) * progressRatio}
          stroke={progress === 100 ? "#10b981" : "#3b82f6"}
          strokeWidth="5"
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0.7 }}
          animate={{ 
            pathLength: 1,
            opacity: progress === 100 ? 1 : 0.8
          }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
        
        {/* Animated data flow particles */}
        {progress < 100 && (
          <>
            {[0, 0.3, 0.6].map((delay, index) => (
              <motion.circle
                key={`particle-${index}`}
                cx={sourceNode.x}
                cy={sourceNode.y}
                r="2"
                fill="#3b82f6"
                initial={{ opacity: 0 }}
                animate={{
                  cx: sourceNode.x + (targetNode.x - sourceNode.x) * progressRatio,
                  cy: sourceNode.y + (targetNode.y - sourceNode.y) * progressRatio,
                  opacity: [0, 1, 1, 0]
                }}
                transition={{
                  duration: 2,
                  delay: delay,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            ))}
          </>
        )}
        
        {/* Progress indicator at transfer point */}
        <motion.g
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
        >
          <circle
            cx={sourceNode.x + (targetNode.x - sourceNode.x) * progressRatio}
            cy={sourceNode.y + (targetNode.y - sourceNode.y) * progressRatio}
            r="12"
            fill={progress === 100 ? "#10b981" : "#3b82f6"}
            stroke="#ffffff"
            strokeWidth="2"
            opacity="0.9"
          />
          <text
            x={sourceNode.x + (targetNode.x - sourceNode.x) * progressRatio}
            y={sourceNode.y + (targetNode.y - sourceNode.y) * progressRatio + 4}
            textAnchor="middle"
            className="text-xs font-bold fill-white"
          >
            {progress}%
          </text>
        </motion.g>
        
        {/* File icon showing transfer */}
        <motion.g
          initial={{ 
            x: sourceNode.x, 
            y: sourceNode.y,
            opacity: 0,
            scale: 0.8
          }}
          animate={{ 
            x: sourceNode.x + (targetNode.x - sourceNode.x) * progressRatio,
            y: sourceNode.y + (targetNode.y - sourceNode.y) * progressRatio,
            opacity: 1,
            scale: progress === 100 ? 1.2 : 1
          }}
          transition={{ 
            duration: 0.6, 
            ease: "easeOut",
            scale: { duration: 0.3 }
          }}
        >
          <circle
            cx="0"
            cy="-25"
            r="10"
            fill="#ffffff"
            stroke={progress === 100 ? "#10b981" : "#3b82f6"}
            strokeWidth="2"
            filter="drop-shadow(2px 2px 4px rgba(0,0,0,0.1))"
          />
          <foreignObject
            x="-8"
            y="-33"
            width="16"
            height="16"
          >
            {progress === 100 ? (
              <CheckCircle className="w-4 h-4 text-green-600" />
            ) : (
              <FileText className="w-4 h-4 text-blue-600" />
            )}
          </foreignObject>
          
          {/* File name label */}
          <rect
            x="-25"
            y="-45"
            width="50"
            height="16"
            rx="8"
            fill="rgba(0,0,0,0.8)"
            opacity="0.9"
          />
          <text
            x="0"
            y="-35"
            textAnchor="middle"
            className="text-xs font-medium fill-white"
          >
            {sync.fileName?.length > 8 ? sync.fileName.slice(0, 8) + '...' : sync.fileName}
          </text>
        </motion.g>

        {/* Transfer speed indicator */}
        {progress > 0 && progress < 100 && (
          <motion.g
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.8 }}
            transition={{ delay: 0.5 }}
          >
            <rect
              x={sourceNode.x + (targetNode.x - sourceNode.x) * 0.5 - 20}
              y={sourceNode.y + (targetNode.y - sourceNode.y) * 0.5 + 15}
              width="40"
              height="14"
              rx="7"
              fill="rgba(59, 130, 246, 0.9)"
              stroke="#ffffff"
              strokeWidth="1"
            />
            <text
              x={sourceNode.x + (targetNode.x - sourceNode.x) * 0.5}
              y={sourceNode.y + (targetNode.y - sourceNode.y) * 0.5 + 24}
              textAnchor="middle"
              className="text-xs font-bold fill-white"
            >
              {sync.action === 'sync_started' ? 'Starting...' : 'Syncing...'}
            </text>
          </motion.g>
        )}

        {/* Completion indicator */}
        {progress === 100 && (
          <motion.g
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
          >
            <circle
              cx={targetNode.x}
              cy={targetNode.y - 30}
              r="8"
              fill="#10b981"
              stroke="#ffffff"
              strokeWidth="2"
            />
            <foreignObject
              x={targetNode.x - 6}
              y={targetNode.y - 36}
              width="12"
              height="12"
            >
              <CheckCircle className="w-3 h-3 text-white" />
            </foreignObject>
          </motion.g>
        )}
      </g>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Network Synchronization</h2>
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span className="text-gray-600">Online</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse"></div>
            <span className="text-gray-600">Syncing</span>
          </div>
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-gray-500" />
            <span className="text-gray-600">{activeSyncs.size} Active</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Network Topology Visualization */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Network Topology</h3>
          
          {networkTopology.length === 0 ? (
            <div className="text-center py-12">
              <Users className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <p className="text-gray-500">No nodes online</p>
            </div>
          ) : (
            <div className="relative">
              <svg width="400" height="400" className="mx-auto">
                {/* Node connections during sync */}
                <AnimatePresence mode="wait">
                  {Array.from(activeSyncs.values()).map((sync) => (
                    <SyncConnection key={sync.uniqueKey} sync={sync} />
                  ))}
                </AnimatePresence>
                
                {/* Nodes */}
                {networkTopology.map((node) => (
                  <g key={`node-${node.node_id}`}>
                    {/* Node circle */}
                    <motion.circle
                      cx={node.x}
                      cy={node.y}
                      r="20"
                      fill={getNodeColor(node)}
                      stroke="#ffffff"
                      strokeWidth="3"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ duration: 0.5 }}
                      className={node.status === 'online' ? 'drop-shadow-lg' : ''}
                    />
                    
                    {/* Node icon */}
                    <foreignObject
                      x={node.x - 8}
                      y={node.y - 8}
                      width="16"
                      height="16"
                    >
                      <Server className="w-4 h-4 text-white" />
                    </foreignObject>
                    
                    {/* Node label */}
                    <text
                      x={node.x}
                      y={node.y + 35}
                      textAnchor="middle"
                      className="text-xs font-medium fill-gray-700"
                    >
                      {node.node_id.slice(0, 8)}...
                    </text>
                    
                    {/* File count badge */}
                    {node.fileCount > 0 && (
                      <g>
                        <circle
                          cx={node.x + 15}
                          cy={node.y - 15}
                          r="8"
                          fill="#ef4444"
                          stroke="#ffffff"
                          strokeWidth="2"
                        />
                        <text
                          x={node.x + 15}
                          y={node.y - 11}
                          textAnchor="middle"
                          className="text-xs font-bold fill-white"
                        >
                          {node.fileCount}
                        </text>
                      </g>
                    )}
                  </g>
                ))}
              </svg>
            </div>
          )}
        </div>

        {/* Activity Feed */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
          
          <div className="space-y-3 max-h-80 overflow-y-auto">
            <AnimatePresence mode="popLayout">
              {activeSyncs.size > 0 && (
                <div className="space-y-2">
                  {Array.from(activeSyncs.values()).map((sync) => (
                    <motion.div
                      key={sync.uniqueKey}
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: 10 }}
                      className={`rounded-lg p-4 border-2 ${
                        sync.progress === 100 
                          ? 'bg-green-50 border-green-300' 
                          : 'bg-blue-50 border-blue-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <motion.div
                            animate={{ 
                              rotate: sync.progress < 100 ? 360 : 0,
                              scale: sync.progress === 100 ? [1, 1.2, 1] : 1
                            }}
                            transition={{ 
                              rotate: { duration: 2, repeat: sync.progress < 100 ? Infinity : 0, ease: "linear" },
                              scale: { duration: 0.5 }
                            }}
                            className={`p-1 rounded-full ${
                              sync.progress === 100 ? 'bg-green-600' : 'bg-blue-600'
                            }`}
                          >
                            {sync.progress === 100 ? (
                              <CheckCircle className="w-4 h-4 text-white" />
                            ) : (
                              <RefreshCw className="w-4 h-4 text-white" />
                            )}
                          </motion.div>
                          <div>
                            <span className={`text-sm font-medium ${
                              sync.progress === 100 ? 'text-green-900' : 'text-blue-900'
                            }`}>
                              {sync.fileName}
                            </span>
                            <div className={`flex items-center space-x-2 text-xs mt-1 ${
                              sync.progress === 100 ? 'text-green-700' : 'text-blue-700'
                            }`}>
                              <span>{sync.sourceNode?.slice(0, 8)}...</span>
                              <ArrowRight className="w-3 h-3" />
                              <span>{sync.targetNode?.slice(0, 8)}...</span>
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-lg font-bold ${
                            sync.progress === 100 ? 'text-green-900' : 'text-blue-900'
                          }`}>
                            {sync.progress}%
                          </div>
                          <div className={`text-xs ${
                            sync.progress === 100 ? 'text-green-700' : 'text-blue-700'
                          }`}>
                            {sync.progress === 100 ? 'Complete' : 
                             sync.action === 'sync_started' ? 'Starting' : 'Syncing'}
                          </div>
                        </div>
                      </div>
                      
                      {/* Enhanced Progress Bar */}
                      <div className="space-y-2">
                        <div className={`w-full rounded-full h-3 overflow-hidden ${
                          sync.progress === 100 ? 'bg-green-200' : 'bg-blue-200'
                        }`}>
                          <motion.div
                            className={`h-full rounded-full relative ${
                              sync.progress === 100 
                                ? 'bg-gradient-to-r from-green-500 to-green-600' 
                                : 'bg-gradient-to-r from-blue-500 to-blue-600'
                            }`}
                            initial={{ width: "0%" }}
                            animate={{ width: `${sync.progress}%` }}
                            transition={{ duration: 0.8, ease: "easeOut" }}
                          >
                            {/* Shimmer effect for active progress */}
                            {sync.progress < 100 && (
                              <motion.div
                                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                                animate={{ x: ['-100%', '200%'] }}
                                transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                              />
                            )}
                            
                            {/* Pulse effect for completion */}
                            {sync.progress === 100 && (
                              <motion.div
                                className="absolute inset-0 bg-white/20 rounded-full"
                                animate={{ opacity: [0, 0.5, 0] }}
                                transition={{ duration: 1, repeat: 2 }}
                              />
                            )}
                          </motion.div>
                        </div>
                        
                        {/* Progress details */}
                        <div className={`flex justify-between text-xs ${
                          sync.progress === 100 ? 'text-green-700' : 'text-blue-700'
                        }`}>
                          <span>
                            {sync.progress === 100 ? (
                              <span className="flex items-center space-x-1">
                                <CheckCircle className="w-3 h-3" />
                                <span>Synchronized successfully</span>
                              </span>
                            ) : (
                              <span className="flex items-center space-x-1">
                                <motion.div
                                  animate={{ opacity: [0.5, 1, 0.5] }}
                                  transition={{ duration: 1.5, repeat: Infinity }}
                                >
                                  <Zap className="w-3 h-3" />
                                </motion.div>
                                <span>
                                  {sync.action === 'sync_started' ? 'Initiating sync...' : 'Transferring data...'}
                                </span>
                              </span>
                            )}
                          </span>
                          <span>
                            {new Date(sync.startTime).toLocaleTimeString()}
                          </span>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
              
              {recentActivity.map((activity) => (
                <motion.div
                  key={activity.id}
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  className={`rounded-lg p-3 border ${
                    activity.type === 'sync_completed' 
                      ? 'bg-green-50 border-green-200' 
                      : activity.type === 'sync_error'
                      ? 'bg-red-50 border-red-200'
                      : activity.type === 'sync_started'
                      ? 'bg-blue-50 border-blue-200'
                      : 'bg-gray-50 border-gray-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      {activity.type === 'sync_completed' ? (
                        <CheckCircle className="w-4 h-4 text-green-600" />
                      ) : activity.type === 'sync_error' ? (
                        <AlertCircle className="w-4 h-4 text-red-600" />
                      ) : activity.type === 'sync_started' ? (
                        <RefreshCw className="w-4 h-4 text-blue-600" />
                      ) : (
                        <FileText className="w-4 h-4 text-gray-600" />
                      )}
                      <span className={`text-sm font-medium ${
                        activity.type === 'sync_completed' ? 'text-green-900' :
                        activity.type === 'sync_error' ? 'text-red-900' :
                        activity.type === 'sync_started' ? 'text-blue-900' :
                        'text-gray-900'
                      }`}>
                        {activity.fileName}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {activity.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                  
                  <div className="mt-1 text-xs text-gray-600">
                    {activity.type === 'sync_completed' ? (
                      <div className="flex items-center space-x-2">
                        <span>{activity.sourceNode?.slice(0, 8)}...</span>
                        <ArrowRight className="w-3 h-3" />
                        <span>{activity.targetNode?.slice(0, 8)}...</span>
                        {activity.bytesTransferred && (
                          <span className="text-green-600 font-medium">
                            • {formatFileSize(activity.bytesTransferred)} transferred
                          </span>
                        )}
                      </div>
                    ) : activity.type === 'sync_error' ? (
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span>{activity.sourceNode?.slice(0, 8)}...</span>
                          <ArrowRight className="w-3 h-3" />
                          <span>{activity.targetNode?.slice(0, 8)}...</span>
                        </div>
                        <div className="text-red-600 font-medium">
                          Error: {activity.error}
                        </div>
                      </div>
                    ) : activity.type === 'sync_started' ? (
                      <div className="flex items-center space-x-2">
                        <span>{activity.sourceNode?.slice(0, 8)}...</span>
                        <ArrowRight className="w-3 h-3" />
                        <span>{activity.targetNode?.slice(0, 8)}...</span>
                        <span className="text-blue-600 font-medium">• Sync initiated</span>
                      </div>
                    ) : (
                      <div>
                        Uploaded to {activity.sourceNode?.slice(0, 8)}...
                        {activity.fileSize && (
                          <span className="text-gray-500">
                            • {formatFileSize(activity.fileSize)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            
            {recentActivity.length === 0 && activeSyncs.size === 0 && (
              <div className="text-center py-8">
                <Activity className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="text-gray-500 text-sm">No recent activity</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SyncVisualization; 