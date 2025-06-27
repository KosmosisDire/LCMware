"""Topic publisher and subscriber classes for LCMware"""

import time
from typing import TypeVar, Generic, Type, Callable, Optional, Protocol
import threading
import logging

from .manager import get_lcm, start_lcm_handler

logger = logging.getLogger(__name__)

# Type variable for message types
MessageT = TypeVar('MessageT', bound='LCMMessage')


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


class TopicPublisher(Generic[MessageT]):
    """Type-safe publisher for a single LCM topic"""
    
    def __init__(self, channel: str, message_type: Type[MessageT]) -> None:
        """
        Initialize topic publisher
        
        Args:
            channel: Full LCM channel name (e.g., "/robot/sensors/camera")
            message_type: LCM message type class
        """
        if not channel:
            raise ValueError("Channel cannot be empty")
        
        # Validate message type at construction time
        _validate_lcm_type(message_type)
        
        self._channel = channel
        self._message_type = message_type
        self._lcm = get_lcm()
        
        logger.info(f"TopicPublisher created for channel '{channel}' with type {message_type.__name__}")
    
    @property
    def channel(self) -> str:
        """Get the channel name"""
        return self._channel
    
    @property
    def message_type(self) -> Type[MessageT]:
        """Get the message type"""
        return self._message_type
    
    def publish(self, message: MessageT) -> None:
        """
        Publish a message to the topic
        
        Args:
            message: LCM message instance of the correct type
            
        Raises:
            TypeError: If message is not of the expected type
        """
        _validate_message_instance(message, self._message_type, "publish")
        
        try:
            self._lcm.publish(self._channel, message.encode())
            logger.debug(f"Published message to '{self._channel}'")
        except Exception as e:
            logger.error(f"Failed to publish to '{self._channel}': {e}")
            raise


class TopicSubscriber(Generic[MessageT]):
    """Type-safe subscriber for a single LCM topic"""
    
    def __init__(self, 
                 channel: str, 
                 message_type: Type[MessageT], 
                 callback: Callable[[MessageT], None]) -> None:
        """
        Initialize topic subscriber
        
        Args:
            channel: Full LCM channel name (e.g., "/robot/sensors/camera")
            message_type: LCM message type class
            callback: Function to call when messages are received
        """
        if not channel:
            raise ValueError("Channel cannot be empty")
        if not callback:
            raise ValueError("Callback cannot be None")
        
        # Validate message type at construction time
        _validate_lcm_type(message_type)
        
        self._channel = channel
        self._message_type = message_type
        self._callback = callback
        self._lcm = get_lcm()
        self._subscription = None
        self._subscribed = False
        self._lock = threading.Lock()
        
        # Auto-subscribe on creation
        self.subscribe()
        
        logger.info(f"TopicSubscriber created for channel '{channel}' with type {message_type.__name__}")
    
    @property
    def channel(self) -> str:
        """Get the channel name"""
        return self._channel
    
    @property
    def message_type(self) -> Type[MessageT]:
        """Get the message type"""
        return self._message_type
    
    @property
    def is_subscribed(self) -> bool:
        """Check if currently subscribed"""
        return self._subscribed
    
    def subscribe(self) -> None:
        """Subscribe to the topic"""
        with self._lock:
            if self._subscribed:
                logger.warning(f"Already subscribed to '{self._channel}'")
                return
            
            try:
                self._subscription = self._lcm.subscribe(self._channel, self._handle_message)
                self._subscribed = True
                
                # Ensure handler thread is running
                start_lcm_handler()
                
                logger.info(f"Subscribed to '{self._channel}'")
            except Exception as e:
                logger.error(f"Failed to subscribe to '{self._channel}': {e}")
                raise
    
    def unsubscribe(self) -> None:
        """Unsubscribe from the topic"""
        with self._lock:
            if not self._subscribed:
                logger.warning(f"Not subscribed to '{self._channel}'")
                return
            
            try:
                if self._subscription:
                    self._lcm.unsubscribe(self._subscription)
                    self._subscription = None
                self._subscribed = False
                logger.info(f"Unsubscribed from '{self._channel}'")
            except Exception as e:
                logger.error(f"Failed to unsubscribe from '{self._channel}': {e}")
                raise
    
    def _handle_message(self, channel: str, data: bytes) -> None:
        """Internal message handler"""
        try:
            # Decode message using the expected type
            message = self._message_type.decode(data)
            
            # Call user callback with typed message
            self._callback(message)
            
            logger.debug(f"Handled message on '{channel}'")
        except Exception as e:
            logger.error(f"Error handling message on '{channel}': {e}")
    
    def __del__(self):
        """Cleanup subscription on deletion"""
        try:
            if self._subscribed:
                self.unsubscribe()
        except:
            pass  # Ignore errors during cleanup