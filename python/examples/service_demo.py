#!/usr/bin/env python3
"""Example demonstrating lcmware service usage with new type-safe API"""

import sys
import logging

from lcmware.types.examples import AddNumbersRequest, AddNumbersResponse
from lcmware import ServiceClient, ServiceServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_server():
    """Run the service server"""
    # Define service handler
    def add_numbers_handler(request: AddNumbersRequest) -> AddNumbersResponse:
        """Add two numbers together"""
        logger.info(f"Received request to add {request.a} + {request.b}")
        result = request.a + request.b
        
        # Create and return response object
        response = AddNumbersResponse()
        response.sum = result
        return response
    
    # Create server for specific service channel with handler
    server = ServiceServer("/demo_robot/add_numbers", AddNumbersRequest, AddNumbersResponse, 
                          add_numbers_handler)
    
    logger.info("Starting service server...")
    server.spin()


def run_client():
    """Run the service client"""
    # Create client for specific service channel
    client = ServiceClient("/demo_robot/add_numbers", AddNumbersRequest, AddNumbersResponse, "math_client")
    
    logger.info("Calling add_numbers service...")
    
    try:
        # Create request object
        request1 = AddNumbersRequest()
        request1.a = 5.0
        request1.b = 3.0
        
        # Call service with typed request
        response: AddNumbersResponse = client.call(request1)
        logger.info(f"Result: {response.sum}")
        
        # Try another call
        request2 = AddNumbersRequest()
        request2.a = 10.5
        request2.b = -6.28
        
        response: AddNumbersResponse = client.call(request2)
        logger.info(f"Result: {response.sum}")
        
    except Exception as e:
        logger.error(f"Service call failed: {e}")


def main():
    """Main entry point"""
    if len(sys.argv) != 2 or sys.argv[1] not in ["server", "client"]:
        print(f"Usage: {sys.argv[0]} [server|client]")
        print("")
        print("This example demonstrates the new type-safe lcmware API:")
        print("- ServiceClient and ServiceServer are bound to specific channels and types")
        print("- No more generic calls with dictionaries - use typed LCM objects")
        print("- Single shared LCM instance managed automatically")
        sys.exit(1)
    
    if sys.argv[1] == "server":
        run_server()
    else:
        run_client()


if __name__ == "__main__":
    main()