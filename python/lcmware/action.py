"""Action client and server implementation for LCMware"""

import time
import uuid
import threading
from typing import TypeVar, Generic, Type, Callable, Optional, List, Protocol
from concurrent.futures import Future, TimeoutError
import logging

from .constants import MAX_CLIENT_NAME_LENGTH, ActionStatus
from .manager import get_lcm, start_lcm_handler

logger = logging.getLogger(__name__)

# Type variables for goal, feedback, and result types
GoalT = TypeVar('GoalT', bound='LCMMessage')
FeedbackT = TypeVar('FeedbackT', bound='LCMMessage')
ResultT = TypeVar('ResultT', bound='LCMMessage')


class LCMMessage(Protocol):
    """Protocol for LCM message types"""
    def encode(self) -> bytes: ...
    
    @classmethod
    def decode(cls, data: bytes) -> 'LCMMessage': ...


def _validate_lcm_type(msg_type: Type) -> None:
    """Validate that a type is a proper LCM message type"""
    if not hasattr(msg_type, 'encode'):
        raise TypeError(f"Type {msg_type.__name__} must have an 'encode' method (not a valid LCM type)")
    if not hasattr(msg_type, 'decode'):
        raise TypeError(f"Type {msg_type.__name__} must have a 'decode' class method (not a valid LCM type)")


def _validate_message_instance(message, expected_type: Type, context: str) -> None:
    """Validate that a message instance is of the expected type"""
    if not isinstance(message, expected_type):
        raise TypeError(f"{context}: Expected {expected_type.__name__}, got {type(message).__name__}")
    
    if not hasattr(message, 'encode'):
        raise TypeError(f"{context}: Message must be an LCM-generated type with encode() method")

def _verify_action_types(goal_type: Type, feedback_type: Type, result_type: Type) -> None:
    """Verify that action goal, feedback, and result types have the correct header structure"""
    # Validate that types are LCM types
    _validate_lcm_type(goal_type)
    _validate_lcm_type(feedback_type)
    _validate_lcm_type(result_type)
    
    # Check goal type structure
    try:
        goal_instance = goal_type()
        if not hasattr(goal_instance, 'header'):
            raise TypeError(f"Action goal type {goal_type.__name__} must have a 'header' field (core.Header)")
        
        # Verify header is the right type (has expected fields)
        if not hasattr(goal_instance.header, 'timestamp_us'):
            raise TypeError(f"Action goal header in {goal_type.__name__} must have 'timestamp_us' field")
        if not hasattr(goal_instance.header, 'id'):
            raise TypeError(f"Action goal header in {goal_type.__name__} must have 'id' field")
    except Exception as e:
        raise TypeError(f"Failed to validate goal type {goal_type.__name__}: {e}")
    
    # Check feedback type structure
    try:
        feedback_instance = feedback_type()
        if not hasattr(feedback_instance, 'header'):
            raise TypeError(f"Action feedback type {feedback_type.__name__} must have a 'header' field (core.Header)")
        
        # Verify feedback header
        if not hasattr(feedback_instance.header, 'timestamp_us'):
            raise TypeError(f"Action feedback header in {feedback_type.__name__} must have 'timestamp_us' field")
        if not hasattr(feedback_instance.header, 'id'):
            raise TypeError(f"Action feedback header in {feedback_type.__name__} must have 'id' field")
    except Exception as e:
        raise TypeError(f"Failed to validate feedback type {feedback_type.__name__}: {e}")
    
    # Check result type structure
    try:
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
    except Exception as e:
        raise TypeError(f"Failed to validate result type {result_type.__name__}: {e}")


class ActionHandle(Generic[GoalT, FeedbackT, ResultT]):
    """Handle for tracking an action goal with type safety"""
    
    def __init__(self, action_client: 'ActionClient[GoalT, FeedbackT, ResultT]', 
                 action_channel: str, goal_id: str):
        self._action_client = action_client
        self._action_channel = action_channel
        self._goal_id = goal_id
        self._result_future = Future()
        self._feedback_callbacks: List[Callable[[FeedbackT], None]] = []
        self._status = ActionStatus.ACCEPTED
        self._cancelled = False
    
    @property
    def goal_id(self) -> str:
        """Get the goal ID"""
        return self._goal_id
    
    @property
    def status(self) -> int:
        """Get the current status"""
        return self._status
    
    @property
    def is_cancelled(self) -> bool:
        """Check if the goal was cancelled"""
        return self._cancelled
        
    def add_feedback_callback(self, callback: Callable[[FeedbackT], None]):
        """Add a callback for feedback updates"""
        if not callback:
            raise ValueError("Callback cannot be None")
        self._feedback_callbacks.append(callback)
        
    def cancel(self):
        """Cancel this action goal"""
        if not self._cancelled and self._status in [ActionStatus.ACCEPTED, ActionStatus.EXECUTING]:
            self._action_client._cancel_goal(self._action_channel, self._goal_id)
            self._cancelled = True
            
    def get_result(self, timeout: Optional[float] = None) -> ResultT:
        """Wait for and return the action result"""
        try:
            return self._result_future.result(timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Action result timed out after {timeout}s")
        
    def _set_feedback(self, feedback: FeedbackT):
        """Internal: called when feedback is received"""
        for callback in self._feedback_callbacks:
            try:
                callback(feedback)
            except Exception as e:
                logger.error(f"Error in feedback callback: {e}")
                
    def _set_result(self, result: ResultT, status: int):
        """Internal: called when result is received"""
        self._status = status
        if not self._result_future.done():
            if status == ActionStatus.SUCCEEDED:
                self._result_future.set_result(result)
            else:
                error_msg = f"Action failed with status {status}"
                self._result_future.set_exception(RuntimeError(error_msg))


class ActionClient(Generic[GoalT, FeedbackT, ResultT]):
    """Type-safe client for calling a specific LCM-RPC action"""
    
    def __init__(self, action_channel: str, goal_type: Type[GoalT], 
                 feedback_type: Type[FeedbackT], result_type: Type[ResultT],
                 client_name: Optional[str] = None):
        """
        Initialize action client for a specific action
        
        Args:
            action_channel: Full action channel path (e.g., "/robot/move_arm")
            goal_type: LCM goal message type class
            feedback_type: LCM feedback message type class
            result_type: LCM result message type class
            client_name: Optional client name (max {MAX_CLIENT_NAME_LENGTH} chars). If not provided, generates one.
        """
        if not action_channel:
            raise ValueError("Action channel cannot be empty")
        
        # Verify types have correct structure
        _verify_action_types(goal_type, feedback_type, result_type)
        
        self._action_channel = action_channel
        self._goal_type = goal_type
        self._feedback_type = feedback_type
        self._result_type = result_type
        
        if client_name:
            if len(client_name) > MAX_CLIENT_NAME_LENGTH:
                raise ValueError(f"Client name must be {MAX_CLIENT_NAME_LENGTH} characters or less, got {len(client_name)}")
            self._client_name = client_name
        else:
            # Generate a short client name if not provided
            self._client_name = f"act_{str(uuid.uuid4())[:5]}"
            
        self._lcm = get_lcm()
        self._active_goals: Dict[str, ActionHandle[GoalT, FeedbackT, ResultT]] = {}  # goal_id -> handle
        self._goal_counter = 0
        self._subscriptions = []
        self._lock = threading.Lock()
        
        logger.info(f"ActionClient created for '{action_channel}' with types {goal_type.__name__} -> {feedback_type.__name__} -> {result_type.__name__}")
    
    @property
    def action_channel(self) -> str:
        """Get the action channel"""
        return self._action_channel
    
    @property
    def goal_type(self) -> Type[GoalT]:
        """Get the goal type"""
        return self._goal_type
    
    @property
    def feedback_type(self) -> Type[FeedbackT]:
        """Get the feedback type"""
        return self._feedback_type
    
    @property
    def result_type(self) -> Type[ResultT]:
        """Get the result type"""
        return self._result_type
    
    def send_goal(self, goal: GoalT) -> ActionHandle[GoalT, FeedbackT, ResultT]:
        """
        Send an action goal
        
        Args:
            goal: LCM goal message instance
            
        Returns:
            ActionHandle for tracking the goal
            
        Raises:
            TypeError: If goal is not of the expected type
        """
        # Validate goal type
        _validate_message_instance(goal, self._goal_type, "send_goal")
        
        # Ensure LCM handler is running
        start_lcm_handler()
        
        # Generate unique goal ID
        self._goal_counter += 1
        goal_id = f"{self._client_name}_{self._goal_counter}"
        
        # Create goal copy with updated header
        goal_copy = self._goal_type()
        # Copy all user fields from original goal (skip built-in methods and header)
        for field_name in dir(goal):
            if (not field_name.startswith('_') and 
                field_name not in ['header', 'encode', 'decode'] and
                hasattr(goal_copy, field_name) and 
                not callable(getattr(goal, field_name, None))):
                try:
                    setattr(goal_copy, field_name, getattr(goal, field_name))
                except (AttributeError, TypeError):
                    pass  # Skip read-only or problematic fields
        
        # Set header fields
        goal_copy.header.timestamp_us = int(time.time() * 1e6)
        goal_copy.header.id = goal_id
        
        # Create action handle
        handle = ActionHandle(self, self._action_channel, goal_id)
        
        with self._lock:
            self._active_goals[goal_id] = handle
        
        # Subscribe to feedback and result channels for this goal
        feedback_channel = f"{self._action_channel}/fb/{goal_id}"
        result_channel = f"{self._action_channel}/res/{goal_id}"
        
        def handle_feedback(channel, data):
            try:
                feedback = self._feedback_type.decode(data)
                with self._lock:
                    if feedback.header.id in self._active_goals:
                        self._active_goals[feedback.header.id]._set_feedback(feedback)
            except Exception as e:
                logger.error(f"Error handling feedback: {e}")
                
        def handle_result(channel, data):
            try:
                result = self._result_type.decode(data)
                goal_id = result.status.header.id
                with self._lock:
                    if goal_id in self._active_goals:
                        result_handle = self._active_goals.pop(goal_id)
                        result_handle._set_result(result, result.status.status)
            except Exception as e:
                logger.error(f"Error handling result: {e}")
        
        fb_sub = self._lcm.subscribe(feedback_channel, handle_feedback)
        res_sub = self._lcm.subscribe(result_channel, handle_result)
        self._subscriptions.extend([fb_sub, res_sub])
        
        # Publish goal
        goal_channel = f"{self._action_channel}/goal"
        self._lcm.publish(goal_channel, goal_copy.encode())
        
        logger.info(f"Sent goal {goal_id} for action '{self._action_channel}'")
        return handle
    
    def stop(self):
        """Stop the action client and clean up subscriptions"""
        with self._lock:
            # Unsubscribe all
            for subscription in self._subscriptions:
                try:
                    self._lcm.unsubscribe(subscription)
                except:
                    pass  # Ignore errors during cleanup
            self._subscriptions.clear()
            self._active_goals.clear()
        
        logger.info(f"ActionClient for '{self._action_channel}' stopped")
    
    def _cancel_goal(self, action_channel: str, goal_id: str):
        """Internal: cancel a specific goal"""
        # Import the ActionCancel type
        from .types.core import ActionCancel
        
        cancel_msg = ActionCancel()
        cancel_msg.header.timestamp_us = int(time.time() * 1e6)
        cancel_msg.header.id = goal_id
        cancel_msg.goal_id = goal_id
        
        cancel_channel = f"{action_channel}/cancel"
        self._lcm.publish(cancel_channel, cancel_msg.encode())
        logger.info(f"Sent cancel request for goal {goal_id}")
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.stop()
        except:
            pass  # Ignore errors during cleanup


class ActionServer(Generic[GoalT, FeedbackT, ResultT]):
    """Type-safe server for providing a specific LCM-RPC action"""
    
    def __init__(self, action_channel: str, goal_type: Type[GoalT], 
                 feedback_type: Type[FeedbackT], result_type: Type[ResultT],
                 handler: Callable[[GoalT, Callable[[FeedbackT], None]], ResultT]):
        """
        Initialize action server for a specific action
        
        Args:
            action_channel: Full action channel path (e.g., "/robot/move_arm")
            goal_type: LCM goal message type class
            feedback_type: LCM feedback message type class
            result_type: LCM result message type class
            handler: Function that takes (goal, feedback_callback) and returns result
        """
        if not action_channel:
            raise ValueError("Action channel cannot be empty")
        if not handler:
            raise ValueError("Handler cannot be None")
        
        # Verify types have correct structure
        _verify_action_types(goal_type, feedback_type, result_type)
        
        self._action_channel = action_channel
        self._goal_type = goal_type
        self._feedback_type = feedback_type
        self._result_type = result_type
        self._handler = handler
        
        self._lcm = get_lcm()
        self._active_goals = {}  # goal_id -> execution_thread
        self._subscriptions = []
        self._running = False
        self._lock = threading.Lock()
        
        logger.info(f"ActionServer created for '{action_channel}' with types {goal_type.__name__} -> {feedback_type.__name__} -> {result_type.__name__}")
    
    @property
    def action_channel(self) -> str:
        """Get the action channel"""
        return self._action_channel
    
    @property
    def goal_type(self) -> Type[GoalT]:
        """Get the goal type"""
        return self._goal_type
    
    @property
    def feedback_type(self) -> Type[FeedbackT]:
        """Get the feedback type"""
        return self._feedback_type
    
    @property
    def result_type(self) -> Type[ResultT]:
        """Get the result type"""
        return self._result_type
    
    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._running
    
    def start(self):
        """Start the action server"""
        with self._lock:
            if self._running:
                logger.warning(f"Action server for '{self._action_channel}' is already running")
                return
            
            try:
                # Import required types
                from .types.core import ActionCancel
                
                # Subscribe to goal and cancel channels
                goal_channel = f"{self._action_channel}/goal"
                cancel_channel = f"{self._action_channel}/cancel"
                
                goal_sub = self._lcm.subscribe(goal_channel, self._handle_goal)
                cancel_sub = self._lcm.subscribe(cancel_channel, self._handle_cancel)
                self._subscriptions.extend([goal_sub, cancel_sub])
                
                self._running = True
                
                # Ensure LCM handler is running
                start_lcm_handler()
                
                logger.info(f"Action server listening on '{goal_channel}' and '{cancel_channel}'")
            except Exception as e:
                logger.error(f"Failed to start action server: {e}")
                raise
    
    def stop(self):
        """Stop the action server"""
        with self._lock:
            if not self._running:
                logger.warning(f"Action server for '{self._action_channel}' is not running")
                return
            
            try:
                # Unsubscribe all
                for subscription in self._subscriptions:
                    self._lcm.unsubscribe(subscription)
                self._subscriptions.clear()
                
                # Wait for active goals to complete (with timeout)
                for goal_id, thread in list(self._active_goals.items()):
                    if thread.is_alive():
                        thread.join(timeout=1.0)  # 1 second timeout
                        if thread.is_alive():
                            logger.warning(f"Goal {goal_id} thread did not finish within timeout")
                
                self._active_goals.clear()
                self._running = False
                
                logger.info(f"Action server for '{self._action_channel}' stopped")
            except Exception as e:
                logger.error(f"Failed to stop action server: {e}")
                raise
    
    def spin(self):
        """Run the server in a blocking loop"""
        self.start()
        try:
            while self._running:
                time.sleep(0.1)  # Wait while LCM handler thread processes messages
        except KeyboardInterrupt:
            logger.info("Action server interrupted")
        finally:
            self.stop()
            
    def handle_once(self, timeout_ms: int = 0):
        """Handle LCM messages once"""
        if not self._running:
            self.start()
        return self._lcm.handle_timeout(timeout_ms)
    
    def _handle_goal(self, channel: str, data: bytes) -> None:
        """Internal goal handler"""
        try:
            goal = self._goal_type.decode(data)
            goal_id = goal.header.id
            
            logger.info(f"Received goal {goal_id} for action '{self._action_channel}'")
            
            # Create feedback callback
            def send_feedback(feedback: FeedbackT):
                """Send feedback for this goal"""
                _validate_message_instance(feedback, self._feedback_type, "send_feedback")
                
                # Set header fields
                feedback.header.timestamp_us = int(time.time() * 1e6)
                feedback.header.id = goal_id
                
                fb_channel = f"{self._action_channel}/fb/{goal_id}"
                self._lcm.publish(fb_channel, feedback.encode())
            
            # Execute action in separate thread
            def execute_action():
                try:
                    result = self._handler(goal, send_feedback)
                    
                    # Validate result type
                    _validate_message_instance(result, self._result_type, "handler result")
                    
                    status = ActionStatus.SUCCEEDED
                    error_msg = ""
                    
                except Exception as e:
                    logger.error(f"Action handler error: {e}")
                    
                    # Create error result
                    result = self._result_type()
                    status = ActionStatus.ABORTED
                    error_msg = str(e)
                
                # Set result status
                result.status.header.timestamp_us = int(time.time() * 1e6)
                result.status.header.id = goal_id
                result.status.status = status
                result.status.message = error_msg
                
                # Send result
                res_channel = f"{self._action_channel}/res/{goal_id}"
                self._lcm.publish(res_channel, result.encode())
                
                # Clean up
                with self._lock:
                    self._active_goals.pop(goal_id, None)
                
                logger.info(f"Action goal {goal_id} completed with status {status}")
            
            # Start execution thread
            exec_thread = threading.Thread(target=execute_action, daemon=True)
            with self._lock:
                self._active_goals[goal_id] = exec_thread
            exec_thread.start()
            
        except Exception as e:
            logger.error(f"Error handling goal: {e}")
    
    def _handle_cancel(self, channel: str, data: bytes) -> None:
        """Internal cancel handler"""
        try:
            from .types.core import ActionCancel
            
            cancel = ActionCancel.decode(data)
            goal_id = cancel.goal_id
            
            with self._lock:
                if goal_id in self._active_goals:
                    logger.info(f"Cancelling goal {goal_id} for action '{self._action_channel}'")
                    # Note: We can't actually stop the thread, but we remove it from tracking
                    # Real implementation would need cooperative cancellation
                    self._active_goals.pop(goal_id, None)
            
        except Exception as e:
            logger.error(f"Error handling cancel: {e}")
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            if self._running:
                self.stop()
        except:
            pass  # Ignore errors during cleanup