#!/usr/bin/env python3
"""Example demonstrating lcmware topic usage with new type-safe API"""

import sys
import time
import logging

from lcmware.types.examples import ImageMessage
from lcmware import TopicPublisher, TopicSubscriber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_publisher():
    """Run the topic publisher"""
    # Create publisher for specific channel and type
    publisher = TopicPublisher("/robot/sensors/camera", ImageMessage)
    
    logger.info("Starting image publisher...")
    
    try:
        for i in range(100):
            # Create image message (small size to avoid UDP buffer issues)
            image = ImageMessage()
            image.width = 720 + (i % 10)  # Small image, vary width slightly
            image.height = 640
            image.channels = 3
            image.encoding = "rgb8"
            # Simple test pattern
            data_list = [i % 256] * (image.width * image.height * image.channels)
            image.data_size = len(data_list)
            image.data = data_list
            
            # Publish with typed object
            publisher.publish(image)
            logger.info(f"Published image {i+1}: {image.width}x{image.height}")
            
            time.sleep(0.1)  # 10 Hz
            
    except KeyboardInterrupt:
        logger.info("Publisher interrupted")


def run_subscriber():
    """Run the topic subscriber"""

    logger.warning("\nNote that you will likely need to increase your system's UDP buffer size to run this demo.\n")

    
    def image_callback(msg: ImageMessage):
        """Handle received image messages"""
        logger.info(f"Received image: {msg.width}x{msg.height}, {msg.channels} channels, "
                   f"encoding: {msg.encoding}, data size: {msg.data_size}")
    
    # Create subscriber for specific channel and type
    subscriber = TopicSubscriber("/robot/sensors/camera", ImageMessage, image_callback)
    
    logger.info("Starting image subscriber...")
    
    try:
        # Keep the subscriber alive
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Subscriber interrupted")
    finally:
        subscriber.unsubscribe()


def run_multi_topic():
    """Demonstrate multiple topics with different message types"""
    from lcmware.types.examples import AddNumbersRequest
    
    def image_callback(msg: ImageMessage):
        logger.info(f"Image: {msg.width}x{msg.height}")
    
    def request_callback(msg: AddNumbersRequest):
        logger.info(f"Request: {msg.a} + {msg.b}")
    
    # Create subscribers for different topics and types
    image_sub = TopicSubscriber("/robot/sensors/camera", ImageMessage, image_callback)
    request_sub = TopicSubscriber("/robot/math/requests", AddNumbersRequest, request_callback)
    
    # Create publishers for different topics and types
    image_pub = TopicPublisher("/robot/sensors/camera", ImageMessage)
    request_pub = TopicPublisher("/robot/math/requests", AddNumbersRequest)
    
    logger.info("Starting multi-topic demo...")
    
    try:
        for i in range(20):
            # Publish image
            image = ImageMessage()
            image.width = 32
            image.height = 24
            image.channels = 3
            image.encoding = "rgb8"
            # Small test pattern
            data_list = [i % 256] * 100
            image.data_size = len(data_list)
            image.data = data_list
            image_pub.publish(image)
            
            # Publish math request
            request = AddNumbersRequest()
            request.a = float(i)
            request.b = float(i * 2)
            request_pub.publish(request)
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        logger.info("Multi-topic demo interrupted")
    finally:
        image_sub.unsubscribe()
        request_sub.unsubscribe()


def main():
    """Main entry point"""
    if len(sys.argv) != 2 or sys.argv[1] not in ["publisher", "subscriber", "multi"]:
        print(f"Usage: {sys.argv[0]} [publisher|subscriber|multi]")
        print("")
        print("This example demonstrates the new type-safe lcmware topic API:")
        print("- TopicPublisher and TopicSubscriber are bound to specific channels and types")
        print("- No more generic publish/subscribe - use typed LCM objects directly")
        print("- Each publisher/subscriber represents a single channel with a single type")
        print("- Single shared LCM instance managed automatically")
        print("")
        print("Run 'publisher' and 'subscriber' in separate terminals to see communication")
        print("Run 'multi' to see multiple topics with different message types")
        sys.exit(1)
    
    if sys.argv[1] == "publisher":
        run_publisher()
    elif sys.argv[1] == "subscriber":
        run_subscriber()
    else:  # multi
        run_multi_topic()


if __name__ == "__main__":
    main()