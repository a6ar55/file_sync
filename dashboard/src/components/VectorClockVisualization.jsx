import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Clock, 
  ArrowRight, 
  AlertTriangle, 
  CheckCircle, 
  RefreshCw,
  Zap,
  GitBranch,
  Target
} from 'lucide-react';

const VectorClockVisualization = ({ events = [] }) => {
  const [vectorClocks, setVectorClocks] = useState({});
  const [causalEvents, setCausalEvents] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [timelineView, setTimelineView] = useState(true);

  // Fetch vector clock data
  useEffect(() => {
    const fetchVectorClocks = async () => {
      try {
        const response = await fetch('/api/vector-clocks');
        if (response.ok) {
          const data = await response.json();
          setVectorClocks(data);
        }
      } catch (error) {
        console.error('Failed to fetch vector clocks:', error);
      }
    };

    fetchVectorClocks();
    const interval = setInterval(fetchVectorClocks, 3000);
    return () => clearInterval(interval);
  }, []);

  // Fetch causal order events
  useEffect(() => {
    const fetchCausalOrder = async () => {
      try {
        const response = await fetch('/api/causal-order?limit=20');
        if (response.ok) {
          const data = await response.json();
          setCausalEvents(data);
        }
      } catch (error) {
        console.error('Failed to fetch causal order:', error);
      }
    };

    fetchCausalOrder();
    const interval = setInterval(fetchCausalOrder, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch conflicts
  useEffect(() => {
    const fetchConflicts = async () => {
      try {
        const response = await fetch('/api/conflicts');
        if (response.ok) {
          const data = await response.json();
          setConflicts(data);
        }
      } catch (error) {
        console.error('Failed to fetch conflicts:', error);
      }
    };

    fetchConflicts();
    const interval = setInterval(fetchConflicts, 10000);
    return () => clearInterval(interval);
  }, []);

  const getEventTypeColor = (eventType) => {
    switch (eventType) {
      case 'file_modified': return '#3b82f6'; // blue
      case 'sync_completed': return '#10b981'; // green
      case 'file_sync_progress': return '#f59e0b'; // yellow
      case 'sync_error': return '#ef4444'; // red
      case 'node_status_change': return '#8b5cf6'; // purple
      default: return '#6b7280'; // gray
    }
  };

  const getRelationshipColor = (relationship) => {
    switch (relationship) {
      case 'before': return '#10b981'; // green
      case 'after': return '#3b82f6'; // blue
      case 'concurrent': return '#ef4444'; // red
      case 'equal': return '#6b7280'; // gray
      default: return '#6b7280';
    }
  };

  const nodeIds = Object.keys(vectorClocks);

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Vector Clock Visualization</h2>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-blue-500" />
            <span className="text-sm text-gray-600">{nodeIds.length} Nodes</span>
          </div>
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-500" />
            <span className="text-sm text-gray-600">{conflicts.length} Conflicts</span>
          </div>
          <button
            onClick={() => setTimelineView(!timelineView)}
            className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200 transition-colors"
          >
            {timelineView ? 'Grid View' : 'Timeline View'}
          </button>
        </div>
      </div>

      {timelineView ? (
        /* Timeline View */
        <div className="space-y-6">
          {/* Vector Clock Grid */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Current Vector Clocks</h3>
            
            {nodeIds.length === 0 ? (
              <div className="text-center py-8">
                <Clock className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                <p className="text-gray-500">No vector clocks available</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-2 px-3 font-medium text-gray-700">Node</th>
                      {nodeIds.map(nodeId => (
                        <th key={nodeId} className="text-center py-2 px-3 font-medium text-gray-700">
                          {nodeId.slice(0, 8)}...
                        </th>
                      ))}
                      <th className="text-center py-2 px-3 font-medium text-gray-700">Max Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nodeIds.map((nodeId, rowIndex) => {
                      const clockData = vectorClocks[nodeId];
                      return (
                        <motion.tr
                          key={nodeId}
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: rowIndex * 0.1 }}
                          className="border-b border-gray-100 hover:bg-gray-50"
                        >
                          <td className="py-2 px-3 font-medium text-gray-900">
                            {nodeId.slice(0, 12)}...
                          </td>
                          {nodeIds.map(colNodeId => {
                            const value = clockData?.clocks[colNodeId] || 0;
                            const isOwnClock = nodeId === colNodeId;
                            return (
                              <td key={colNodeId} className="text-center py-2 px-3">
                                <motion.div
                                  className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold ${
                                    isOwnClock 
                                      ? 'bg-blue-600 text-white' 
                                      : value > 0 
                                        ? 'bg-green-100 text-green-800' 
                                        : 'bg-gray-100 text-gray-500'
                                  }`}
                                  whileHover={{ scale: 1.1 }}
                                  animate={isOwnClock ? { 
                                    scale: [1, 1.1, 1],
                                    backgroundColor: ['#2563eb', '#3b82f6', '#2563eb']
                                  } : {}}
                                  transition={{ duration: 2, repeat: Infinity }}
                                >
                                  {value}
                                </motion.div>
                              </td>
                            );
                          })}
                          <td className="text-center py-2 px-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded-full text-xs font-medium">
                              {clockData?.max_time || 0}
                            </span>
                          </td>
                        </motion.tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Causal Order Timeline */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Event Timeline (Causal Order)</h3>
            
            <div className="relative">
              {causalEvents.length === 0 ? (
                <div className="text-center py-8">
                  <GitBranch className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                  <p className="text-gray-500">No events in timeline</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Timeline line */}
                  <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gray-300"></div>
                  
                  {causalEvents.map((event, index) => (
                    <motion.div
                      key={event.event_id}
                      initial={{ opacity: 0, x: -50 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.1 }}
                      className={`relative flex items-center space-x-4 p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedEvent?.event_id === event.event_id 
                          ? 'bg-blue-100 border border-blue-300' 
                          : 'bg-white hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedEvent(selectedEvent?.event_id === event.event_id ? null : event)}
                    >
                      {/* Timeline dot */}
                      <div 
                        className="absolute left-6 w-4 h-4 rounded-full border-2 border-white z-10"
                        style={{ backgroundColor: getEventTypeColor(event.event_type) }}
                      ></div>
                      
                      {/* Event content */}
                      <div className="ml-12 flex-1">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-3">
                            <span 
                              className="px-2 py-1 text-xs font-medium rounded-full text-white"
                              style={{ backgroundColor: getEventTypeColor(event.event_type) }}
                            >
                              {event.event_type.replace(/_/g, ' ').toUpperCase()}
                            </span>
                            <span className="text-sm font-medium text-gray-900">
                              Node: {event.node_id.slice(0, 8)}...
                            </span>
                            {event.vector_clock && (
                              <span className="text-xs text-gray-500 font-mono">
                                {Object.values(event.vector_clock.clocks || {}).join(', ')}
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-gray-500">
                            {new Date(event.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        
                        {event.data && (
                          <div className="mt-1 text-sm text-gray-600">
                            {event.data.file_name && `File: ${event.data.file_name}`}
                            {event.data.action && ` • Action: ${event.data.action}`}
                            {event.data.progress && ` • Progress: ${event.data.progress}%`}
                          </div>
                        )}

                        {/* Expanded details */}
                        <AnimatePresence>
                          {selectedEvent?.event_id === event.event_id && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              className="mt-3 p-3 bg-gray-100 rounded text-xs"
                            >
                              <div className="grid grid-cols-2 gap-2">
                                <div><strong>Event ID:</strong> {event.event_id}</div>
                                <div><strong>File ID:</strong> {event.file_id || 'N/A'}</div>
                                <div><strong>Processed:</strong> {event.processed ? 'Yes' : 'No'}</div>
                                <div><strong>Vector Clock:</strong> {JSON.stringify(event.vector_clock?.clocks || {})}</div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Conflict Detection */}
          {conflicts.length > 0 && (
            <div className="bg-red-50 rounded-lg p-4 border border-red-200">
              <h3 className="text-lg font-medium text-red-900 mb-4 flex items-center">
                <AlertTriangle className="w-5 h-5 mr-2" />
                Detected Conflicts
              </h3>
              
              <div className="space-y-3">
                {conflicts.map((conflict, index) => (
                  <motion.div
                    key={conflict.conflict_id}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.1 }}
                    className="bg-white rounded-lg p-3 border border-red-300"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-red-900">
                        File ID: {conflict.file_id}
                      </span>
                      <span className="text-xs text-red-700">
                        {new Date(conflict.detected_at).toLocaleString()}
                      </span>
                    </div>
                    
                    <div className="text-sm text-red-800">
                      Concurrent modifications between:
                      <span className="font-mono ml-1">{conflict.node1.slice(0, 8)}...</span>
                      <ArrowRight className="w-4 h-4 inline mx-2" />
                      <span className="font-mono">{conflict.node2.slice(0, 8)}...</span>
                    </div>
                    
                    {!conflict.is_resolved && (
                      <div className="mt-2 flex space-x-2">
                        <button className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 transition-colors">
                          Resolve Conflict
                        </button>
                        <button className="px-3 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors">
                          View Details
                        </button>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Grid View */
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Vector Clock Grid View</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {nodeIds.map((nodeId, index) => {
              const clockData = vectorClocks[nodeId];
              return (
                <motion.div
                  key={nodeId}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="bg-white rounded-lg p-4 shadow-sm border"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-medium text-gray-900 truncate">
                      {nodeId.slice(0, 16)}...
                    </h4>
                    <span className="text-xs text-gray-500">
                      Max: {clockData?.max_time || 0}
                    </span>
                  </div>
                  
                  <div className="space-y-2">
                    {Object.entries(clockData?.clocks || {}).map(([clockNodeId, value]) => (
                      <div key={clockNodeId} className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 truncate">
                          {clockNodeId.slice(0, 8)}...
                        </span>
                        <motion.span
                          className={`px-2 py-1 rounded-full text-xs font-medium ${
                            clockNodeId === nodeId 
                              ? 'bg-blue-100 text-blue-800' 
                              : 'bg-gray-100 text-gray-700'
                          }`}
                          animate={clockNodeId === nodeId ? { scale: [1, 1.1, 1] } : {}}
                          transition={{ duration: 2, repeat: Infinity }}
                        >
                          {value}
                        </motion.span>
                      </div>
                    ))}
                  </div>
                  
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <div className="text-xs text-gray-500">
                      Display: <span className="font-mono">{clockData?.display || '[]'}</span>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default VectorClockVisualization; 