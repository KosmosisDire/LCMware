#include <iostream>
#include <string>
#include <lcmware/service.hpp>
#include <lcmware/types/examples/AddNumbersRequest.hpp>
#include <lcmware/types/examples/AddNumbersResponse.hpp>

using namespace lcmware;

void run_server() {
    std::cout << "Starting service server..." << std::endl;
    
    // Define service handler
    auto add_numbers_handler = [](const examples::AddNumbersRequest& request) -> examples::AddNumbersResponse {
        std::cout << "Received request to add " << request.a << " + " << request.b << std::endl;
        
        examples::AddNumbersResponse response;
        response.sum = request.a + request.b;
        
        return response;
    };
    
    // Create server for specific service channel with handler
    ServiceServer<examples::AddNumbersRequest, examples::AddNumbersResponse> server(
        "/demo_robot/add_numbers", add_numbers_handler);
    
    // Run server
    server.spin();
}

void run_client() {
    std::cout << "Starting service client..." << std::endl;
    
    // Create client for specific service channel
    ServiceClient<examples::AddNumbersRequest, examples::AddNumbersResponse> client(
        "/demo_robot/add_numbers", "cpp_math_cli");
    
    try {
        // First call
        std::cout << "Calling add_numbers service..." << std::endl;
        examples::AddNumbersRequest request1;
        request1.a = 5.0;
        request1.b = 3.0;
        
        auto response1 = client.call(request1);
        std::cout << "Result: " << response1.sum << std::endl;
        
        // Second call
        examples::AddNumbersRequest request2;
        request2.a = 10.5;
        request2.b = -6.28;
        
        auto response2 = client.call(request2);
        std::cout << "Result: " << response2.sum << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Service call failed: " << e.what() << std::endl;
    }
}

int main(int argc, char* argv[]) {
    if (argc != 2 || (std::string(argv[1]) != "server" && std::string(argv[1]) != "client")) {
        std::cerr << "Usage: " << argv[0] << " [server|client]" << std::endl;
        std::cerr << "" << std::endl;
        std::cerr << "This example demonstrates the new type-safe lcmware C++ API:" << std::endl;
        std::cerr << "- ServiceClient and ServiceServer are bound to specific channels and types" << std::endl;
        std::cerr << "- No more generic calls - use typed LCM objects directly" << std::endl;
        std::cerr << "- Single shared LCM instance managed automatically" << std::endl;
        return 1;
    }
    
    if (std::string(argv[1]) == "server") {
        run_server();
    } else {
        run_client();
    }
    
    return 0;
}