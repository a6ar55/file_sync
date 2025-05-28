"""
Vector clock implementation for maintaining causal ordering in distributed file synchronization.
"""

from enum import Enum
from typing import Dict, Set, Optional, List
import json
import logging
from datetime import datetime


class ClockComparison(Enum):
    """Possible relationships between two vector clocks."""
    BEFORE = "before"      # First clock happened before second
    AFTER = "after"        # First clock happened after second
    CONCURRENT = "concurrent"  # Clocks are concurrent (conflict potential)
    EQUAL = "equal"        # Clocks are identical


class VectorClock:
    """
    Vector clock implementation for distributed systems.
    
    Each node maintains a vector clock to track causal relationships
    between events across the distributed system.
    """
    
    def __init__(self, node_id: str, initial_clocks: Dict[str, int] = None):
        """
        Initialize vector clock for a specific node.
        
        Args:
            node_id: Unique identifier for this node
            initial_clocks: Optional initial clock values
        """
        self.node_id = node_id
        self.clocks: Dict[str, int] = initial_clocks.copy() if initial_clocks else {}
        
        # Ensure our own node is in the clock
        if node_id not in self.clocks:
            self.clocks[node_id] = 0
    
    def increment(self) -> 'VectorClock':
        """
        Increment this node's clock value.
        Call this when a local event occurs.
        
        Returns:
            Self for method chaining
        """
        self.clocks[self.node_id] += 1
        logging.debug(f"Node {self.node_id} incremented clock to {self.clocks[self.node_id]}")
        return self
    
    def update(self, other: 'VectorClock') -> 'VectorClock':
        """
        Update this clock with another clock (message receive).
        Takes the maximum of each component and increments own clock.
        
        Args:
            other: The other vector clock to merge
            
        Returns:
            Self for method chaining
        """
        if not isinstance(other, VectorClock):
            raise ValueError("Can only update with another VectorClock")
        
        # Get all known nodes
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        
        # Update each component to max value
        for node in all_nodes:
            self_val = self.clocks.get(node, 0)
            other_val = other.clocks.get(node, 0)
            self.clocks[node] = max(self_val, other_val)
        
        # Increment our own clock
        self.clocks[self.node_id] += 1
        
        logging.debug(f"Node {self.node_id} updated clock after receiving message: {self.clocks}")
        return self
    
    def compare(self, other: 'VectorClock') -> ClockComparison:
        """
        Compare this clock with another to determine causal relationship.
        
        Args:
            other: The other vector clock to compare
            
        Returns:
            ClockComparison indicating the relationship
        """
        if not isinstance(other, VectorClock):
            raise ValueError("Can only compare with another VectorClock")
        
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        
        self_greater = False
        other_greater = False
        
        for node in all_nodes:
            self_val = self.clocks.get(node, 0)
            other_val = other.clocks.get(node, 0)
            
            if self_val > other_val:
                self_greater = True
            elif other_val > self_val:
                other_greater = True
        
        # Determine relationship
        if self_greater and not other_greater:
            return ClockComparison.AFTER
        elif other_greater and not self_greater:
            return ClockComparison.BEFORE
        elif not self_greater and not other_greater:
            return ClockComparison.EQUAL
        else:
            return ClockComparison.CONCURRENT
    
    def is_concurrent_with(self, other: 'VectorClock') -> bool:
        """Check if this clock is concurrent with another (potential conflict)."""
        return self.compare(other) == ClockComparison.CONCURRENT
    
    def happened_before(self, other: 'VectorClock') -> bool:
        """Check if this clock happened before another."""
        return self.compare(other) == ClockComparison.BEFORE
    
    def happened_after(self, other: 'VectorClock') -> bool:
        """Check if this clock happened after another."""
        return self.compare(other) == ClockComparison.AFTER
    
    def copy(self) -> 'VectorClock':
        """Create a deep copy of this vector clock."""
        return VectorClock(self.node_id, self.clocks.copy())
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "clocks": self.clocks.copy(),
            "timestamp": datetime.now().isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> 'VectorClock':
        """Create VectorClock from dictionary."""
        return cls(data["node_id"], data["clocks"])
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'VectorClock':
        """Create VectorClock from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def get_nodes(self) -> Set[str]:
        """Get all known nodes in this clock."""
        return set(self.clocks.keys())
    
    def get_clock_value(self, node_id: str) -> int:
        """Get clock value for a specific node."""
        return self.clocks.get(node_id, 0)
    
    def __str__(self) -> str:
        """String representation of the vector clock."""
        clock_items = [f"{node}:{value}" for node, value in sorted(self.clocks.items())]
        return f"VectorClock({self.node_id})[{', '.join(clock_items)}]"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other) -> bool:
        """Check equality with another vector clock."""
        if not isinstance(other, VectorClock):
            return False
        return self.compare(other) == ClockComparison.EQUAL
    
    def __lt__(self, other) -> bool:
        """Check if this clock is less than (happened before) another."""
        return self.happened_before(other)
    
    def __gt__(self, other) -> bool:
        """Check if this clock is greater than (happened after) another."""
        return self.happened_after(other)


class VectorClockManager:
    """
    Manager for vector clocks across multiple nodes.
    Handles clock operations and conflict detection.
    """
    
    def __init__(self):
        """Initialize the vector clock manager."""
        self.node_clocks: Dict[str, VectorClock] = {}
        self.event_history: List[Dict] = []
    
    def register_node(self, node_id: str) -> VectorClock:
        """
        Register a new node and create its vector clock.
        
        Args:
            node_id: Unique identifier for the node
            
        Returns:
            The created vector clock for the node
        """
        if node_id in self.node_clocks:
            logging.warning(f"Node {node_id} already registered, returning existing clock")
            return self.node_clocks[node_id]
        
        # Initialize with all known nodes
        initial_clocks = {}
        for existing_node in self.node_clocks:
            initial_clocks[existing_node] = 0
        
        clock = VectorClock(node_id, initial_clocks)
        self.node_clocks[node_id] = clock
        
        # Update all existing clocks to include the new node
        for existing_clock in self.node_clocks.values():
            if existing_clock.node_id != node_id:
                existing_clock.clocks[node_id] = 0
        
        logging.info(f"Registered new node {node_id} with vector clock")
        return clock
    
    def get_clock(self, node_id: str) -> Optional[VectorClock]:
        """Get the vector clock for a specific node."""
        return self.node_clocks.get(node_id)
    
    def record_event(self, node_id: str, event_type: str, data: Dict = None) -> VectorClock:
        """
        Record an event for a node and increment its clock.
        
        Args:
            node_id: The node where the event occurred
            event_type: Type of event (file_created, file_modified, etc.)
            data: Optional event data
            
        Returns:
            The updated vector clock
        """
        if node_id not in self.node_clocks:
            self.register_node(node_id)
        
        clock = self.node_clocks[node_id]
        clock.increment()
        
        # Record in history
        event_record = {
            "node_id": node_id,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "vector_clock": clock.to_dict(),
            "data": data or {}
        }
        self.event_history.append(event_record)
        
        logging.debug(f"Recorded event {event_type} for node {node_id}")
        return clock.copy()
    
    def sync_clocks(self, sender_id: str, receiver_id: str, sender_clock: VectorClock) -> VectorClock:
        """
        Synchronize clocks when a message is sent between nodes.
        
        Args:
            sender_id: ID of the sending node
            receiver_id: ID of the receiving node
            sender_clock: Vector clock from the sender
            
        Returns:
            Updated vector clock for the receiver
        """
        if receiver_id not in self.node_clocks:
            self.register_node(receiver_id)
        
        receiver_clock = self.node_clocks[receiver_id]
        receiver_clock.update(sender_clock)
        
        logging.debug(f"Synchronized clocks between {sender_id} and {receiver_id}")
        return receiver_clock.copy()
    
    def detect_conflicts(self, file_id: str, node1_id: str, node2_id: str) -> bool:
        """
        Detect if there's a conflict between two nodes for a file.
        
        Args:
            file_id: The file being checked for conflicts
            node1_id: First node ID
            node2_id: Second node ID
            
        Returns:
            True if conflict detected, False otherwise
        """
        if node1_id not in self.node_clocks or node2_id not in self.node_clocks:
            return False
        
        clock1 = self.node_clocks[node1_id]
        clock2 = self.node_clocks[node2_id]
        
        is_concurrent = clock1.is_concurrent_with(clock2)
        
        if is_concurrent:
            logging.warning(f"Conflict detected for file {file_id} between nodes {node1_id} and {node2_id}")
        
        return is_concurrent
    
    def get_causal_order(self, events: List[Dict]) -> List[Dict]:
        """
        Sort events in causal order based on their vector clocks.
        
        Args:
            events: List of events with vector clock information
            
        Returns:
            Events sorted in causal order
        """
        def compare_events(event1, event2):
            clock1 = VectorClock.from_dict(event1["vector_clock"])
            clock2 = VectorClock.from_dict(event2["vector_clock"])
            
            comparison = clock1.compare(clock2)
            if comparison == ClockComparison.BEFORE:
                return -1
            elif comparison == ClockComparison.AFTER:
                return 1
            else:
                # For concurrent events, use timestamp as tiebreaker
                return -1 if event1["timestamp"] < event2["timestamp"] else 1
        
        from functools import cmp_to_key
        return sorted(events, key=cmp_to_key(compare_events))
    
    def get_system_state(self) -> Dict:
        """Get the current state of all vector clocks in the system."""
        return {
            "nodes": {node_id: clock.to_dict() for node_id, clock in self.node_clocks.items()},
            "total_events": len(self.event_history),
            "last_event": self.event_history[-1] if self.event_history else None
        }
    
    def cleanup_history(self, max_events: int = 1000):
        """Clean up old events from history to prevent memory bloat."""
        if len(self.event_history) > max_events:
            self.event_history = self.event_history[-max_events:]
            logging.info(f"Cleaned up event history, kept last {max_events} events") 