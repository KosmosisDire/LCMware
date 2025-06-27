#!/usr/bin/env python3
"""Example demonstrating LCMware service usage"""

import sys
import logging

from lcmware.types.examples import AddNumbersRequest, AddNumbersResponse
from lcmware import ServiceClient, ServiceServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_server():
    """Run the service server"""
    server = ServiceServer("demo_robot")
    
    # Define service handler
    def add_numbers_handler(request: AddNumbersRequest) -> dict:
        """Add two numbers together"""
        logger.info(f"Received request to add {request.a} + {request.b}")
        result = request.a + request.b
        return {"sum": result}
    
    # Register service
    server.register_service("add_numbers", AddNumbersRequest, AddNumbersResponse, 
                           add_numbers_handler)
    
    logger.info("Starting service server...")
    server.spin()


def run_client():
    """Run the service client"""
    client = ServiceClient("demo_robot", "math_client")
    
    logger.info("Calling add_numbers service...")
    
    try:
        # Call service
        response: AddNumbersResponse = client.call("add_numbers", AddNumbersRequest, AddNumbersResponse, {
            "a": 5.0,
            "b": 3.0
        })
        
        logger.info(f"Result: {response.sum}")
        
        # Try another call
        response: AddNumbersResponse = client.call("add_numbers", AddNumbersRequest, AddNumbersResponse, {
            "a": 10.5,
            "b": -6.28
        })
        
        logger.info(f"Result: {response.sum}")
        
    except Exception as e:
        logger.error(f"Service call failed: {e}")
    finally:
        client.stop()


def main():
    """Main entry point"""
    if len(sys.argv) != 2 or sys.argv[1] not in ["server", "client"]:
        print(f"Usage: {sys.argv[0]} [server|client]")
        sys.exit(1)
    
    if sys.argv[1] == "server":
        run_server()
    else:
        run_client()


if __name__ == "__main__":
    main()