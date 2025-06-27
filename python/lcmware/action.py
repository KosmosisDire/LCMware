"""Action client and server implementation for LCMware"""

import lcm
import time
import uuid
import threading
from typing import Type, Callable, Any, Dict, Optional, List
from concurrent.futures import Future, TimeoutError
import logging

from .constants import MAX_CLIENT_NAME_LENGTH, ACTION_ACCEPTED, ACTION_EXECUTING, ACTION_SUCCEEDED, ACTION_ABORTED, ACTION_CANCELED

logger = logging.getLogger(__name__)

# Type verification cache to avoid repeated verification
_verified_action_types = set()

def _verify_action_types(action_name: str, goal_type: Type, feedback_type: Type, result_type: Type):
    """Verify that action goal, feedback, and result types have the correct header structure"""
    type_key = (action_name, goal_type.__name__, feedback_type.__name__, result_type.__name__)
    
    if type_key in _verified_action_types:
        return  # Already verified
    
    logger.info(f"Verifying action types for '{action_name}'...")
    
    # Check goal type
    goal_instance = goal_type()
    if not hasattr(goal_instance, 'header'):
        raise TypeError(f"Action goal type {goal_type.__name__} must have a 'header' field (core.Header)")
    
    # Verify header is the right type (has expected fields)
    if not hasattr(goal_instance.header, 'timestamp_us'):
        raise TypeError(f"Action goal header in {goal_type.__name__} must have 'timestamp_us' field")
    if not hasattr(goal_instance.header, 'id'):
        raise TypeError(f"Action goal header in {goal_type.__name__} must have 'id' field")
    
    # Check feedback type
    feedback_instance = feedback_type()
    if not hasattr(feedback_instance, 'header'):
        raise TypeError(f"Action feedback type {feedback_type.__name__} must have a 'header' field (core.Header)")
    
    # Verify feedback header
    if not hasattr(feedback_instance.header, 'timestamp_us'):
        raise TypeError(f"Action feedback header in {feedback_type.__name__} must have 'timestamp_us' field")
    if not hasattr(feedback_instance.header, 'id'):
        raise TypeError(f"Action feedback header in {feedback_type.__name__} must have 'id' field")
    
    # Check result type - can have either 'status' field or 'response_header' field
    result_instance = result_type()
    has_status = hasattr(result_instance, 'status')
    has_response_header = hasattr(result_instance, 'response_header')
    
    if not (has_status or has_response_header):
        raise TypeError(f"Action result type {result_type.__name__} must have either a 'status' field (core.ActionStatus) or 'response_header' field (core.ServiceResponseHeader)")
    
    if has_status:
        # Verify ActionStatus structure
        if not hasattr(result_instance.status, 'header'):
            raise TypeError(f"Action result status in {result_type.__name__} must have a 'header' field")
        if not hasattr(result_instance.status, 'status'):
            raise TypeError(f"Action result status in {result_type.__name__} must have a 'status' field")
        if not hasattr(result_instance.status, 'message'):
            raise TypeError(f"Action result status in {result_type.__name__} must have a 'message' field")
    
    if has_response_header:
        # Verify ServiceResponseHeader structure  
        if not hasattr(result_instance.response_header, 'header'):
            raise TypeError(f"Action result response_header in {result_type.__name__} must have a 'header' field")
        if not hasattr(result_instance.response_header, 'success'):
            raise TypeError(f"Action result response_header in {result_type.__name__} must have a 'success' field")
        if not hasattr(result_instance.response_header, 'error_message'):
            raise TypeError(f"Action result response_header in {result_type.__name__} must have an 'error_message' field")
    
    _verified_action_types.add(type_key)
    logger.info(f"Action types for '{action_name}' verified successfully")


class ActionHandle:
    """Handle for tracking an action goal"""
    
    def __init__(self, action_client, action_name: str, goal_id: str):
        self.action_client = action_client
        self.action_name = action_name
        self.goal_id = goal_id
        self._result_future = Future()
        self._feedback_callbacks: List[Callable[[Any], None]] = []
        self._status = ACTION_ACCEPTED
        self._cancelled = False
        
    def add_feedback_callback(self, callback: Callable[[Any], None]):
        """Add a callback for feedback updates"""
        self._feedback_callbacks.append(callback)
        
    def cancel(self):
        """Cancel this action goal"""
        if not self._cancelled and self._status in [ACTION_ACCEPTED, ACTION_EXECUTING]:
            self.action_client._cancel_goal(self.action_name, self.goal_id)
            self._cancelled = True
            
    def get_result(self, timeout: Optional[float] = None):
        """Wait for and return the action result"""
        return self._result_future.result(timeout=timeout)
        
    def _set_feedback(self, feedback):
        """Internal: called when feedback is received"""
        for callback in self._feedback_callbacks:
            try:
                callback(feedback)
            except Exception as e:
                logger.error(f"Error in feedback callback: {e}")
                
    def _set_result(self, result, status: int):
        """Internal: called when result is received"""
        self._status = status
        if not self._result_future.done():
            if status == ACTION_SUCCEEDED:
                self._result_future.set_result(result)
            else:
                error_msg = f"Action failed with status {status}"
                self._result_future.set_exception(RuntimeError(error_msg))


class ActionClient:
    """Client for calling LCM-RPC actions"""
    
    def __init__(self, namespace: str, client_name: Optional[str] = None,
                 lcm_instance: Optional[lcm.LCM] = None):
        """
        Initialize action client
        
        Args:
            namespace: Robot namespace (e.g., "my_robot")
            client_name: Optional client name (max {MAX_CLIENT_NAME_LENGTH} chars). If not provided, generates one.
            lcm_instance: Optional LCM instance to reuse
        """
        self.namespace = namespace
        if client_name:
            if len(client_name) > MAX_CLIENT_NAME_LENGTH:
                raise ValueError(f"Client name must be {MAX_CLIENT_NAME_LENGTH} characters or less, got {len(client_name)}")
            self.client_name = client_name
        else:
            # Generate a short client name if not provided
            self.client_name = f"act_{str(uuid.uuid4())[:5]}"
            
        self.lcm = lcm_instance or lcm.LCM()
        self._active_goals: Dict[str, ActionHandle] = {}  # goal_id -> handle
        self._goal_counter = 0
        self._handler_thread = None
        self._running = False
        self._subscriptions = []
        
    def start(self):
        """Start the LCM handler thread"""
        if not self._running:
            self._running = True
            self._handler_thread = threading.Thread(target=self._handle_loop, daemon=True)
            self._handler_thread.start()
            
    def stop(self):
        """Stop the LCM handler thread"""
        self._running = False
        if self._handler_thread:
            self._handler_thread.join()
        # Unsubscribe all
        for subscription in self._subscriptions:
            self.lcm.unsubscribe(subscription)
        self._subscriptions.clear()
            
    def _handle_loop(self):
        """LCM message handling loop"""
        while self._running:
            self.lcm.handle_timeout(100)  # 100ms timeout
            
    def send_goal(self, action_name: str, goal_type: Type, feedback_type: Type,
                  result_type: Type, goal_data: Dict[str, Any]) -> ActionHandle:
        """
        Send an action goal
        
        Args:
            action_name: Name of the action
            goal_type: LCM goal message type class
            feedback_type: LCM feedback message type class
            result_type: LCM result message type class
            goal_data: Dictionary of goal fields
            
        Returns:
            ActionHandle for tracking the goal
        """
        # Verify types have correct structure (only on first use)
        _verify_action_types(action_name, goal_type, feedback_type, result_type)
        
        # Ensure handler is running
        if not self._running:
            self.start()
            
        # Generate unique goal ID
        self._goal_counter += 1
        goal_id = f"{self.client_name}_{self._goal_counter}"
        
        # Create goal message
        goal = goal_type()
        goal.header.timestamp_us = int(time.time() * 1e6)
        goal.header.id = goal_id
        
        # Set goal fields
        for key, value in goal_data.items():
            if hasattr(goal, key):
                setattr(goal, key, value)
            else:
                raise ValueError(f"Goal type {goal_type.__name__} has no field '{key}'")
        
        # Create action handle
        handle = ActionHandle(self, action_name, goal_id)
        self._active_goals[goal_id] = handle
        
        # Subscribe to feedback and result channels for this goal
        feedback_channel = f"/{self.namespace}/act/{action_name}/fb/{goal_id}"
        result_channel = f"/{self.namespace}/act/{action_name}/res/{goal_id}"
        
        def handle_feedback(channel, data):
            try:
                feedback = feedback_type.decode(data)
                if feedback.header.id in self._active_goals:
                    self._active_goals[feedback.header.id]._set_feedback(feedback)
            except Exception as e:
                logger.error(f"Error handling feedback: {e}")
                
        def handle_result(channel, data):
            try:
                result = result_type.decode(data)
                goal_id = result.status.header.id
                if goal_id in self._active_goals:
                    handle = self._active_goals.pop(goal_id)
                    handle._set_result(result, result.status.status)
            except Exception as e:
                logger.error(f"Error handling result: {e}")
        
        fb_sub = self.lcm.subscribe(feedback_channel, handle_feedback)
        res_sub = self.lcm.subscribe(result_channel, handle_result)
        self._subscriptions.extend([fb_sub, res_sub])
        
        # Publish goal
        goal_channel = f"/{self.namespace}/act/{action_name}/goal"
        self.lcm.publish(goal_channel, goal.encode())
        
        logger.info(f"Sent goal {goal_id} for action {action_name}")
        return handle
        
    def _cancel_goal(self, action_name: str, goal_id: str):
        """Internal: cancel a specific goal"""
        # Import the ActionCancel type
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(script_dir, '../../../lcm_types'))
        from lcmware.types.core import ActionCancel
        
        cancel_msg = ActionCancel()
        cancel_msg.header.timestamp_us = int(time.time() * 1e6)
        cancel_msg.header.id = goal_id
        cancel_msg.goal_id = goal_id
        
        cancel_channel = f"/{self.namespace}/act/{action_name}/cancel"
        self.lcm.publish(cancel_channel, cancel_msg.encode())
        logger.info(f"Sent cancel request for goal {goal_id}")


class ActionServer:
    """Server for providing LCM-RPC actions"""
    
    def __init__(self, namespace: str, lcm_instance: Optional[lcm.LCM] = None):
        """
        Initialize action server
        
        Args:
            namespace: Robot namespace (e.g., "my_robot")
            lcm_instance: Optional LCM instance to reuse
        """
        self.namespace = namespace
        self.lcm = lcm_instance or lcm.LCM()
        self._actions = {}  # action_name -> (goal_type, feedback_type, result_type, handler)
        self._active_goals = {}  # goal_id -> execution_thread
        self._subscriptions = []
        self._running = False
        
    def register_action(self, action_name: str, goal_type: Type, feedback_type: Type,
                       result_type: Type, handler: Callable):
        """
        Register an action handler
        
        Args:
            action_name: Name of the action
            goal_type: LCM goal message type class
            feedback_type: LCM feedback message type class
            result_type: LCM result message type class
            handler: Function that takes (goal, feedback_callback) and returns result_dict
        """
        if self._running:
            raise RuntimeError("Cannot register action while server is running")
        
        # Verify types have correct structure
        _verify_action_types(action_name, goal_type, feedback_type, result_type)
            
        self._actions[action_name] = (goal_type, feedback_type, result_type, handler)
        
    def start(self):
        """Start the action server"""
        if self._running:
            return
            
        # Import required types
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(script_dir, '../../../lcm_types'))
        from lcmware.types.core import ActionCancel
        
        # Subscribe to goal and cancel channels for all actions
        for action_name, (goal_type, feedback_type, result_type, handler) in self._actions.items():
            goal_channel = f"/{self.namespace}/act/{action_name}/goal"
            cancel_channel = f"/{self.namespace}/act/{action_name}/cancel"
            
            def create_goal_handler(act_name, g_type, f_type, r_type, act_handler):
                def handle_goal(channel, data):
                    try:
                        goal = g_type.decode(data)
                        goal_id = goal.header.id
                        
                        logger.info(f"Received goal {goal_id} for action {act_name}")
                        
                        # Create feedback callback
                        def send_feedback(feedback_data: Dict[str, Any], progress: float = 0.0):
                            feedback = f_type()
                            feedback.header.timestamp_us = int(time.time() * 1e6)
                            feedback.header.id = goal_id
                            feedback.progress = progress
                            
                            # Set feedback fields
                            for key, value in feedback_data.items():
                                if hasattr(feedback, key):
                                    setattr(feedback, key, value)
                            
                            fb_channel = f"/{self.namespace}/act/{act_name}/fb/{goal_id}"
                            self.lcm.publish(fb_channel, feedback.encode())
                        
                        # Execute action in separate thread
                        def execute_action():
                            try:
                                result_data = act_handler(goal, send_feedback)
                                status = ACTION_SUCCEEDED
                                error_msg = ""
                            except Exception as e:
                                logger.error(f"Action {act_name} handler error: {e}")
                                result_data = {}
                                status = ACTION_ABORTED
                                error_msg = str(e)
                            
                            # Send result
                            result = r_type()
                            result.status.header.timestamp_us = int(time.time() * 1e6)
                            result.status.header.id = goal_id
                            result.status.status = status
                            result.status.message = error_msg
                            
                            # Set result fields
                            for key, value in result_data.items():
                                if hasattr(result, key):
                                    setattr(result, key, value)
                            
                            res_channel = f"/{self.namespace}/act/{act_name}/res/{goal_id}"
                            self.lcm.publish(res_channel, result.encode())
                            
                            # Clean up
                            self._active_goals.pop(goal_id, None)
                            logger.info(f"Action {act_name} goal {goal_id} completed with status {status}")
                        
                        # Start execution thread
                        exec_thread = threading.Thread(target=execute_action, daemon=True)
                        self._active_goals[goal_id] = exec_thread
                        exec_thread.start()
                        
                    except Exception as e:
                        logger.error(f"Error handling goal for {act_name}: {e}")
                
                return handle_goal
            
            def create_cancel_handler(act_name):
                def handle_cancel(channel, data):
                    try:
                        cancel = ActionCancel.decode(data)
                        goal_id = cancel.goal_id
                        
                        if goal_id in self._active_goals:
                            logger.info(f"Cancelling goal {goal_id} for action {act_name}")
                            # Note: We can't actually stop the thread, but we remove it from tracking
                            # Real implementation would need cooperative cancellation
                            self._active_goals.pop(goal_id, None)
                        
                    except Exception as e:
                        logger.error(f"Error handling cancel for {act_name}: {e}")
                
                return handle_cancel
            
            goal_handler = create_goal_handler(action_name, goal_type, feedback_type, result_type, handler)
            cancel_handler = create_cancel_handler(action_name)
            
            goal_sub = self.lcm.subscribe(goal_channel, goal_handler)
            cancel_sub = self.lcm.subscribe(cancel_channel, cancel_handler)
            self._subscriptions.extend([goal_sub, cancel_sub])
            
            logger.info(f"Action {action_name} listening on {goal_channel}")
        
        self._running = True
        
    def stop(self):
        """Stop the action server"""
        if not self._running:
            return
            
        # Unsubscribe all
        for subscription in self._subscriptions:
            self.lcm.unsubscribe(subscription)
        self._subscriptions.clear()
        self._running = False
        
    def spin(self):
        """Run the server in a blocking loop"""
        self.start()
        try:
            while True:
                self.lcm.handle()
        except KeyboardInterrupt:
            logger.info("Action server interrupted")
        finally:
            self.stop()
            
    def handle_once(self, timeout_ms: int = 0):
        """Handle LCM messages once"""
        if not self._running:
            self.start()
        return self.lcm.handle_timeout(timeout_ms)