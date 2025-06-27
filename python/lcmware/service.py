"""Service client and server implementation for LCMware"""

import time
import uuid
import threading
from typing import TypeVar, Generic, Type, Callable, Optional, Protocol
from concurrent.futures import Future, TimeoutError
import logging

from .constants import MAX_CLIENT_NAME_LENGTH
from .manager import get_lcm, start_lcm_handler

logger = logging.getLogger(__name__)

# Type variables for request and response types
RequestT = TypeVar('RequestT', bound='LCMMessage')
ResponseT = TypeVar('ResponseT', bound='LCMMessage')


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

def _verify_service_types(request_type: Type, response_type: Type) -> None:
    """Verify that service request and response types have the correct header structure"""
    # Validate that types are LCM types
    _validate_lcm_type(request_type)
    _validate_lcm_type(response_type)
    
    # Check request type structure
    try:
        request_instance = request_type()
        if not hasattr(request_instance, 'header'):
            raise TypeError(f"Service request type {request_type.__name__} must have a 'header' field (core.Header)")
        
        # Verify header is the right type (has expected fields)
        if not hasattr(request_instance.header, 'timestamp_us'):
            raise TypeError(f"Service request header in {request_type.__name__} must have 'timestamp_us' field")
        if not hasattr(request_instance.header, 'id'):
            raise TypeError(f"Service request header in {request_type.__name__} must have 'id' field")
    except Exception as e:
        raise TypeError(f"Failed to validate request type {request_type.__name__}: {e}")
    
    # Check response type structure
    try:
        response_instance = response_type()
        if not hasattr(response_instance, 'response_header'):
            raise TypeError(f"Service response type {response_type.__name__} must have a 'response_header' field (core.ServiceResponseHeader)")
        
        # Verify response_header structure
        if not hasattr(response_instance.response_header, 'header'):
            raise TypeError(f"Service response_header in {response_type.__name__} must have a 'header' field")
        if not hasattr(response_instance.response_header, 'success'):
            raise TypeError(f"Service response_header in {response_type.__name__} must have a 'success' field")
        if not hasattr(response_instance.response_header, 'error_message'):
            raise TypeError(f"Service response_header in {response_type.__name__} must have an 'error_message' field")
        
        # Verify nested header in response
        if not hasattr(response_instance.response_header.header, 'timestamp_us'):
            raise TypeError(f"Service response header in {response_type.__name__} must have 'timestamp_us' field")
        if not hasattr(response_instance.response_header.header, 'id'):
            raise TypeError(f"Service response header in {response_type.__name__} must have 'id' field")
    except Exception as e:
        raise TypeError(f"Failed to validate response type {response_type.__name__}: {e}")


class ServiceClient(Generic[RequestT, ResponseT]):
    """Type-safe client for calling a specific LCM-RPC service"""
    
    def __init__(self, service_channel: str, request_type: Type[RequestT], 
                 response_type: Type[ResponseT], client_name: Optional[str] = None):
        """
        Initialize service client for a specific service
        
        Args:
            service_channel: Full service channel path (e.g., "/robot/add_numbers")
            request_type: LCM request message type class
            response_type: LCM response message type class
            client_name: Optional client name (max {MAX_CLIENT_NAME_LENGTH} chars). If not provided, generates one.
        """
        if not service_channel:
            raise ValueError("Service channel cannot be empty")
        
        # Verify types have correct structure
        _verify_service_types(request_type, response_type)
        
        self._service_channel = service_channel
        self._request_type = request_type
        self._response_type = response_type
        
        if client_name:
            if len(client_name) > MAX_CLIENT_NAME_LENGTH:
                raise ValueError(f"Client name must be {MAX_CLIENT_NAME_LENGTH} characters or less, got {len(client_name)}")
            self._client_name = client_name
        else:
            # Generate a short client name if not provided
            self._client_name = f"cli_{str(uuid.uuid4())[:5]}"
        
        self._lcm = get_lcm()
        self._responses = {}  # request_id -> Future
        self._response_lock = threading.Lock()
        self._request_counter = 0  # For generating unique request IDs
        
        logger.info(f"ServiceClient created for '{service_channel}' with types {request_type.__name__} -> {response_type.__name__}")
    
    @property
    def service_channel(self) -> str:
        """Get the service channel"""
        return self._service_channel
    
    @property
    def request_type(self) -> Type[RequestT]:
        """Get the request type"""
        return self._request_type
    
    @property
    def response_type(self) -> Type[ResponseT]:
        """Get the response type"""
        return self._response_type
    
    def call(self, request: RequestT, timeout: float = 5.0) -> ResponseT:
        """
        Call the service with a request and wait for response
        
        Args:
            request: LCM request message instance
            timeout: Timeout in seconds
            
        Returns:
            Response message object
            
        Raises:
            TypeError: If request is not of the expected type
            TimeoutError: If no response within timeout
            RuntimeError: If service call fails
        """
        # Validate request type
        _validate_message_instance(request, self._request_type, "call")
        
        # Ensure LCM handler is running
        start_lcm_handler()
        
        # Create request copy with updated header
        request_copy = self._request_type()
        # Copy all user fields from original request (skip built-in methods and header)
        for field_name in dir(request):
            if (not field_name.startswith('_') and 
                field_name not in ['header', 'encode', 'decode'] and
                hasattr(request_copy, field_name) and 
                not callable(getattr(request, field_name, None))):
                try:
                    setattr(request_copy, field_name, getattr(request, field_name))
                except (AttributeError, TypeError):
                    pass  # Skip read-only or problematic fields
        
        # Set header fields
        request_copy.header.timestamp_us = int(time.time() * 1e6)
        
        # Generate unique request ID using client name + counter
        self._request_counter += 1
        request_copy.header.id = f"{self._client_name}_{self._request_counter}"
        
        # Create future for response
        future = Future()
        with self._response_lock:
            self._responses[request_copy.header.id] = future
        
        # Subscribe to response channel
        response_channel = f"{self._service_channel}/rsp/{request_copy.header.id}"
        
        def handle_response(channel, data):
            try:
                response = self._response_type.decode(data)
                with self._response_lock:
                    if response.response_header.header.id in self._responses:
                        response_future = self._responses.pop(response.response_header.header.id)
                        if response.response_header.success:
                            response_future.set_result(response)
                        else:
                            response_future.set_exception(RuntimeError(response.response_header.error_message))
            except Exception as e:
                logger.error(f"Error handling response: {e}")
        
        subscription = self._lcm.subscribe(response_channel, handle_response)
        
        try:
            # Publish request
            request_channel = f"{self._service_channel}/req"
            self._lcm.publish(request_channel, request_copy.encode())
            
            # Wait for response
            response = future.result(timeout=timeout)
            return response
        except TimeoutError:
            with self._response_lock:
                self._responses.pop(request_copy.header.id, None)
            raise TimeoutError(f"Service call to '{self._service_channel}' timed out after {timeout}s")
        finally:
            # Unsubscribe
            self._lcm.unsubscribe(subscription)


class ServiceServer(Generic[RequestT, ResponseT]):
    """Type-safe server for providing a specific LCM-RPC service"""
    
    def __init__(self, service_channel: str, request_type: Type[RequestT], 
                 response_type: Type[ResponseT], handler: Callable[[RequestT], ResponseT]):
        """
        Initialize service server for a specific service
        
        Args:
            service_channel: Full service channel path (e.g., "/robot/add_numbers")
            request_type: LCM request message type class
            response_type: LCM response message type class
            handler: Function that takes request object and returns response object
        """
        if not service_channel:
            raise ValueError("Service channel cannot be empty")
        if not handler:
            raise ValueError("Handler cannot be None")
        
        # Verify types have correct structure
        _verify_service_types(request_type, response_type)
        
        self._service_channel = service_channel
        self._request_type = request_type
        self._response_type = response_type
        self._handler = handler
        
        self._lcm = get_lcm()
        self._subscription = None
        self._running = False
        self._lock = threading.Lock()
        
        logger.info(f"ServiceServer created for '{service_channel}' with types {request_type.__name__} -> {response_type.__name__}")
    
    @property
    def service_channel(self) -> str:
        """Get the service channel"""
        return self._service_channel
    
    @property
    def request_type(self) -> Type[RequestT]:
        """Get the request type"""
        return self._request_type
    
    @property
    def response_type(self) -> Type[ResponseT]:
        """Get the response type"""
        return self._response_type
    
    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._running
    
    def start(self):
        """Start the service server"""
        with self._lock:
            if self._running:
                logger.warning(f"Service server for '{self._service_channel}' is already running")
                return
            
            try:
                # Subscribe to request channel
                request_channel = f"{self._service_channel}/req"
                self._subscription = self._lcm.subscribe(request_channel, self._handle_request)
                self._running = True
                
                # Ensure LCM handler is running
                start_lcm_handler()
                
                logger.info(f"Service server listening on '{request_channel}'")
            except Exception as e:
                logger.error(f"Failed to start service server: {e}")
                raise
    
    def stop(self):
        """Stop the service server"""
        with self._lock:
            if not self._running:
                logger.warning(f"Service server for '{self._service_channel}' is not running")
                return
            
            try:
                if self._subscription:
                    self._lcm.unsubscribe(self._subscription)
                    self._subscription = None
                self._running = False
                logger.info(f"Service server for '{self._service_channel}' stopped")
            except Exception as e:
                logger.error(f"Failed to stop service server: {e}")
                raise
    
    def spin(self):
        """Run the server in a blocking loop"""
        self.start()
        try:
            while self._running:
                time.sleep(0.1)  # Wait while LCM handler thread processes messages
        except KeyboardInterrupt:
            logger.info("Service server interrupted")
        finally:
            self.stop()
    
    def handle_once(self, timeout_ms: int = 0):
        """Handle LCM messages once"""
        if not self._running:
            self.start()
        return self._lcm.handle_timeout(timeout_ms)
    
    def _handle_request(self, channel: str, data: bytes) -> None:
        """Internal request handler"""
        try:
            # Decode request
            request = self._request_type.decode(data)
            
            # Call user handler
            try:
                response = self._handler(request)
                
                # Validate response type
                _validate_message_instance(response, self._response_type, "handler response")
                
                # Set success status
                response.response_header.success = True
                response.response_header.error_message = ""
                
            except Exception as e:
                logger.error(f"Service handler error: {e}")
                
                # Create error response
                response = self._response_type()
                response.response_header.success = False
                response.response_header.error_message = str(e)
            
            # Set response header
            response.response_header.header.timestamp_us = int(time.time() * 1e6)
            response.response_header.header.id = request.header.id
            
            # Publish response
            response_channel = f"{self._service_channel}/rsp/{request.header.id}"
            self._lcm.publish(response_channel, response.encode())
            
            logger.debug(f"Handled request on '{channel}'")
            
        except Exception as e:
            logger.error(f"Error handling request on '{channel}': {e}")
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            if self._running:
                self.stop()
        except:
            pass  # Ignore errors during cleanup