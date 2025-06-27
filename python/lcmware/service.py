"""Service client and server implementation for LCMware"""

import lcm
import time
import uuid
import threading
from typing import Type, Callable, Any, Dict, Optional
from concurrent.futures import Future, TimeoutError
import logging

from .constants import MAX_CLIENT_NAME_LENGTH

logger = logging.getLogger(__name__)

# Type verification cache to avoid repeated verification
_verified_service_types = set()

def _verify_service_types(service_name: str, request_type: Type, response_type: Type):
    """Verify that service request and response types have the correct header structure"""
    type_key = (service_name, request_type.__name__, response_type.__name__)
    
    if type_key in _verified_service_types:
        return  # Already verified
    
    logger.info(f"Verifying service types for '{service_name}'...")
    
    # Check request type
    request_instance = request_type()
    if not hasattr(request_instance, 'header'):
        raise TypeError(f"Service request type {request_type.__name__} must have a 'header' field (core.Header)")
    
    # Verify header is the right type (has expected fields)
    if not hasattr(request_instance.header, 'timestamp_us'):
        raise TypeError(f"Service request header in {request_type.__name__} must have 'timestamp_us' field")
    if not hasattr(request_instance.header, 'id'):
        raise TypeError(f"Service request header in {request_type.__name__} must have 'id' field")
    
    # Check response type
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
    
    _verified_service_types.add(type_key)
    logger.info(f"Service types for '{service_name}' verified successfully")


class ServiceClient:
    """Client for calling LCM-RPC services"""
    
    def __init__(self, namespace: str, client_name: Optional[str] = None, 
                 lcm_instance: Optional[lcm.LCM] = None):
        """
        Initialize service client
        
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
            self.client_name = f"cli_{str(uuid.uuid4())[:5]}"
        
        self.lcm = lcm_instance or lcm.LCM()
        self._responses = {}  # request_id -> Future
        self._response_lock = threading.Lock()
        self._handler_thread = None
        self._running = False
        self._request_counter = 0  # For generating unique request IDs
        
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
            
    def _handle_loop(self):
        """LCM message handling loop"""
        while self._running:
            self.lcm.handle_timeout(100)  # 100ms timeout
            
    def call(self, service_name: str, request_type: Type, response_type: Type, 
             request_data: Dict[str, Any], timeout: float = 5.0) -> Any:
        """
        Call a service and wait for response
        
        Args:
            service_name: Name of the service
            request_type: LCM request message type class
            response_type: LCM response message type class
            request_data: Dictionary of request fields
            timeout: Timeout in seconds
            
        Returns:
            Response message object
            
        Raises:
            TimeoutError: If no response within timeout
            RuntimeError: If service call fails
        """
        # Verify types have correct structure (only on first use)
        _verify_service_types(service_name, request_type, response_type)
        
        # Ensure handler is running
        if not self._running:
            self.start()
            
        # Create request with client-based ID for readable channels
        request = request_type()
        request.header.timestamp_us = int(time.time() * 1e6)
        
        # Generate unique request ID using client name + counter
        self._request_counter += 1
        request.header.id = f"{self.client_name}_{self._request_counter}"
        
        # Set request fields
        for key, value in request_data.items():
            if hasattr(request, key):
                setattr(request, key, value)
            else:
                raise ValueError(f"Request type {request_type.__name__} has no field '{key}'")
        
        # Create future for response
        future = Future()
        with self._response_lock:
            self._responses[request.header.id] = future
        
        # Subscribe to response channel (keep under 63 chars)
        response_channel = f"/{self.namespace}/svc/{service_name}/rsp/{request.header.id}"
        
        def handle_response(channel, data):
            try:
                response = response_type.decode(data)
                with self._response_lock:
                    if response.response_header.header.id in self._responses:
                        future = self._responses.pop(response.response_header.header.id)
                        if response.response_header.success:
                            future.set_result(response)
                        else:
                            future.set_exception(RuntimeError(response.response_header.error_message))
            except Exception as e:
                logger.error(f"Error handling response: {e}")
        
        subscription = self.lcm.subscribe(response_channel, handle_response)
        
        # Publish request
        request_channel = f"/{self.namespace}/svc/{service_name}/req"
        self.lcm.publish(request_channel, request.encode())
        
        try:
            # Wait for response
            response = future.result(timeout=timeout)
            return response
        except TimeoutError:
            with self._response_lock:
                self._responses.pop(request.header.id, None)
            raise TimeoutError(f"Service {service_name} call timed out after {timeout}s")
        finally:
            # Unsubscribe
            self.lcm.unsubscribe(subscription)


class ServiceServer:
    """Server for providing LCM-RPC services"""
    
    def __init__(self, namespace: str, lcm_instance: Optional[lcm.LCM] = None):
        """
        Initialize service server
        
        Args:
            namespace: Robot namespace (e.g., "my_robot")
            lcm_instance: Optional LCM instance to reuse
        """
        self.namespace = namespace
        self.lcm = lcm_instance or lcm.LCM()
        self._services = {}  # service_name -> (request_type, response_type, handler)
        self._subscriptions = []
        self._running = False
        
    def register_service(self, service_name: str, request_type: Type, response_type: Type,
                        handler: Callable[[Any], Dict[str, Any]]):
        """
        Register a service handler
        
        Args:
            service_name: Name of the service
            request_type: LCM request message type class
            response_type: LCM response message type class  
            handler: Function that takes request object and returns response dict
        """
        if self._running:
            raise RuntimeError("Cannot register service while server is running")
        
        # Verify types have correct structure
        _verify_service_types(service_name, request_type, response_type)
            
        self._services[service_name] = (request_type, response_type, handler)
        
    def start(self):
        """Start the service server"""
        if self._running:
            return
            
        # Subscribe to all service request channels
        for service_name, (request_type, response_type, handler) in self._services.items():
            request_channel = f"/{self.namespace}/svc/{service_name}/req"
            
            def create_handler(svc_name, req_type, resp_type, svc_handler):
                def handle_request(channel, data):
                    try:
                        # Decode request
                        request = req_type.decode(data)
                        
                        # Call handler
                        try:
                            response_data = svc_handler(request)
                            success = True
                            error_message = ""
                        except Exception as e:
                            logger.error(f"Service {svc_name} handler error: {e}")
                            response_data = {}
                            success = False
                            error_message = str(e)
                        
                        # Create response
                        response = resp_type()
                        response.response_header.header.timestamp_us = int(time.time() * 1e6)
                        response.response_header.header.id = request.header.id
                        response.response_header.success = success
                        response.response_header.error_message = error_message
                        
                        # Set response fields
                        for key, value in response_data.items():
                            if hasattr(response, key):
                                setattr(response, key, value)
                        
                        # Publish response
                        response_channel = f"/{self.namespace}/svc/{svc_name}/rsp/{request.header.id}"
                        self.lcm.publish(response_channel, response.encode())
                        
                    except Exception as e:
                        logger.error(f"Error handling request for {svc_name}: {e}")
                
                return handle_request
            
            handler_func = create_handler(service_name, request_type, response_type, handler)
            subscription = self.lcm.subscribe(request_channel, handler_func)
            self._subscriptions.append(subscription)
            logger.info(f"Service {service_name} listening on {request_channel}")
        
        self._running = True
        
    def stop(self):
        """Stop the service server"""
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
            logger.info("Service server interrupted")
        finally:
            self.stop()
            
    def handle_once(self, timeout_ms: int = 0):
        """Handle LCM messages once"""
        if not self._running:
            self.start()
        return self.lcm.handle_timeout(timeout_ms)