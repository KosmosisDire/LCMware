#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <vector>
#include <lcmware/topic.hpp>
#include <lcmware/types/examples/ImageMessage.hpp>
#include <lcmware/types/examples/AddNumbersRequest.hpp>

using namespace lcmware;

void run_publisher() {
    std::cout << "Starting image publisher..." << std::endl;
    
    // Create publisher for specific channel and type
    TopicPublisher<examples::ImageMessage> publisher("/robot/sensors/camera");
    
    try {
        for (int i = 0; i < 100; ++i) {
            // Create image message (small size to avoid UDP buffer issues)
            examples::ImageMessage image;
            image.width = 720 + (i % 10);  // Small image, vary width slightly
            image.height = 640;
            image.channels = 3;
            image.encoding = "rgb8";
            
            // Create simple test pattern
            int data_size = image.width * image.height * image.channels;
            image.data_size = data_size;
            image.data.resize(data_size, i % 256);
            
            // Publish with typed object
            publisher.publish(image);
            std::cout << "Published image " << (i+1) << ": " << image.width << "x" << image.height << std::endl;
            
            std::this_thread::sleep_for(std::chrono::milliseconds(100));  // 10 Hz
        }
        
    } catch (const std::exception& e) {
        std::cout << "Publisher interrupted: " << e.what() << std::endl;
    }
}

void run_subscriber() {
    std::cout << "Starting image subscriber..." << std::endl;
    
    // Define callback for received images
    auto image_callback = [](const examples::ImageMessage& msg) {
        std::cout << "Received image: " << msg.width << "x" << msg.height 
                 << ", " << msg.channels << " channels, "
                 << "encoding: " << msg.encoding 
                 << ", data size: " << msg.data_size << std::endl;
    };
    
    // Create subscriber for specific channel and type
    TopicSubscriber<examples::ImageMessage> subscriber("/robot/sensors/camera", image_callback);
    
    try {
        // Keep the subscriber alive
        while (true) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    } catch (const std::exception& e) {
        std::cout << "Subscriber interrupted: " << e.what() << std::endl;
    }
}

void run_multi_topic() {
    std::cout << "Starting multi-topic demo..." << std::endl;
    
    // Define callbacks for different message types
    auto image_callback = [](const examples::ImageMessage& msg) {
        std::cout << "Image: " << msg.width << "x" << msg.height << std::endl;
    };
    
    auto request_callback = [](const examples::AddNumbersRequest& msg) {
        std::cout << "Request: " << msg.a << " + " << msg.b << std::endl;
    };
    
    // Create subscribers for different topics and types
    TopicSubscriber<examples::ImageMessage> image_sub("/robot/sensors/camera", image_callback);
    TopicSubscriber<examples::AddNumbersRequest> request_sub("/robot/math/requests", request_callback);
    
    // Create publishers for different topics and types
    TopicPublisher<examples::ImageMessage> image_pub("/robot/sensors/camera");
    TopicPublisher<examples::AddNumbersRequest> request_pub("/robot/math/requests");
    
    try {
        for (int i = 0; i < 20; ++i) {
            // Publish image
            examples::ImageMessage image;
            image.width = 32;
            image.height = 24;
            image.channels = 3;
            image.encoding = "rgb8";
            image.data_size = 100;
            image.data.resize(100, i % 256);  // Small test pattern
            image_pub.publish(image);
            
            // Publish math request
            examples::AddNumbersRequest request;
            request.a = static_cast<double>(i);
            request.b = static_cast<double>(i * 2);
            request_pub.publish(request);
            
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }
        
    } catch (const std::exception& e) {
        std::cout << "Multi-topic demo interrupted: " << e.what() << std::endl;
    }
}

int main(int argc, char* argv[]) {
    if (argc != 2 || (std::string(argv[1]) != "publisher" && 
                     std::string(argv[1]) != "subscriber" && 
                     std::string(argv[1]) != "multi")) {
        std::cerr << "Usage: " << argv[0] << " [publisher|subscriber|multi]" << std::endl;
        std::cerr << "" << std::endl;
        std::cerr << "This example demonstrates the new type-safe LCMware C++ topic API:" << std::endl;
        std::cerr << "- TopicPublisher and TopicSubscriber are bound to specific channels and types" << std::endl;
        std::cerr << "- No more generic publish/subscribe - use typed LCM objects directly" << std::endl;
        std::cerr << "- Each publisher/subscriber represents a single channel with a single type" << std::endl;
        std::cerr << "- Single shared LCM instance managed automatically" << std::endl;
        std::cerr << "" << std::endl;
        std::cerr << "Run 'publisher' and 'subscriber' in separate terminals to see communication" << std::endl;
        std::cerr << "Run 'multi' to see multiple topics with different message types" << std::endl;
        return 1;
    }
    
    std::string mode = argv[1];
    
    if (mode == "publisher") {
        run_publisher();
    } else if (mode == "subscriber") {
        run_subscriber();
    } else {  // multi
        run_multi_topic();
    }
    
    return 0;
}