#pragma once

#include <lcm/lcm-cpp.hpp>
#include <functional>
#include <unordered_map>
#include <future>
#include <thread>
#include <mutex>
#include <atomic>
#include <string>
#include <memory>
#include <chrono>
#include <stdexcept>
#include <random>
#include "constants.hpp"
#include "manager.hpp"

namespace lcmware {

template<typename RequestType, typename ResponseType>
class ServiceClient {
public:
    /**
     * @brief Initialize service client for a specific service
     * @param service_channel Full service channel path (e.g., "/robot/add_numbers")
     * @param client_name Optional client name (max 16 chars). If empty, generates one.
     */
    ServiceClient(const std::string& service_channel, const std::string& client_name = "");
    ~ServiceClient();
    
    /**
     * @brief Get the service channel
     * @return The service channel
     */
    const std::string& getServiceChannel() const { return service_channel_; }
    
    /**
     * @brief Call the service with a request and wait for response
     * @param request LCM request message instance
     * @param timeout_seconds Timeout in seconds
     * @return Response message object
     * @throws std::runtime_error If service call fails or times out
     */
    ResponseType call(const RequestType& request, double timeout_seconds = 5.0);

private:
    class ResponseHandler {
    public:
        ServiceClient* client;
        
        void handleMessage(const lcm::ReceiveBuffer* rbuf,
                          const std::string& chan,
                          const ResponseType* msg) {
            client->handle_response(msg);
        }
    };

    std::string service_channel_;
    std::string client_name_;
    std::shared_ptr<lcm::LCM> lcm_;
    std::unordered_map<std::string, std::promise<ResponseType>> responses_;
    std::mutex response_mutex_;
    int request_counter_;
    ResponseHandler response_handler_;
    
    void handle_response(const ResponseType* response);
    std::string generate_client_name();
    void verify_client_name(const std::string& name);
};

template<typename RequestType, typename ResponseType>
class ServiceServer {
public:
    using ServiceHandler = std::function<ResponseType(const RequestType&)>;

    /**
     * @brief Initialize service server for a specific service
     * @param service_channel Full service channel path (e.g., "/robot/add_numbers")
     * @param handler Function that takes request object and returns response object
     */
    ServiceServer(const std::string& service_channel, ServiceHandler handler);
    ~ServiceServer();
    
    /**
     * @brief Get the service channel
     * @return The service channel
     */
    const std::string& getServiceChannel() const { return service_channel_; }
    
    /**
     * @brief Check if server is running
     * @return True if running, false otherwise
     */
    bool isRunning() const { return running_; }

    void start();
    void stop();
    void spin();
    bool handle_once(int timeout_ms = 0);

private:
    class RequestHandler {
    public:
        ServiceServer* server;
        std::string service_name;
        
        void handleMessage(const lcm::ReceiveBuffer* rbuf,
                          const std::string& chan,
                          const RequestType* msg) {
            server->handle_request(chan, msg);
        }
    };

    std::string service_channel_;
    ServiceHandler handler_;
    std::shared_ptr<lcm::LCM> lcm_;
    lcm::Subscription* subscription_;
    std::unique_ptr<RequestHandler> request_handler_;
    std::atomic<bool> running_;
    std::mutex mutex_;
    
    void handle_request(const std::string& channel, const RequestType* request);
};

// ServiceClient Implementation

template<typename RequestType, typename ResponseType>
ServiceClient<RequestType, ResponseType>::ServiceClient(
    const std::string& service_channel, const std::string& client_name)
    : service_channel_(service_channel), request_counter_(0) {
    
    if (service_channel_.empty()) {
        throw std::invalid_argument("Service channel cannot be empty");
    }
    
    if (client_name.empty()) {
        client_name_ = generate_client_name();
    } else {
        verify_client_name(client_name);
        client_name_ = client_name;
    }
    
    lcm_ = getLCM();
    response_handler_.client = this;
}

template<typename RequestType, typename ResponseType>
ServiceClient<RequestType, ResponseType>::~ServiceClient() {
    // No explicit cleanup needed - LCM managed by singleton
}


template<typename RequestType, typename ResponseType>
ResponseType ServiceClient<RequestType, ResponseType>::call(
    const RequestType& request, double timeout_seconds) {
    
    // Ensure LCM handler is running
    startLCMHandler();
    
    // Create request with unique ID
    RequestType req_copy = request;
    auto now = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    req_copy.header.timestamp_us = now;
    req_copy.header.id = client_name_ + "_" + std::to_string(++request_counter_);
    
    // Setup response handling
    std::promise<ResponseType> response_promise;
    auto response_future = response_promise.get_future();
    
    {
        std::lock_guard<std::mutex> lock(response_mutex_);
        responses_[req_copy.header.id] = std::move(response_promise);
    }
    
    // Subscribe to response channel
    std::string response_channel = service_channel_ + "/rsp/" + req_copy.header.id;
    auto subscription = lcm_->subscribe(response_channel, 
        &ResponseHandler::handleMessage, &response_handler_);
    
    try {
        // Publish request
        std::string request_channel = service_channel_ + "/req";
        lcm_->publish(request_channel, &req_copy);
        
        // Wait for response
        auto status = response_future.wait_for(std::chrono::duration<double>(timeout_seconds));
        if (status == std::future_status::timeout) {
            std::lock_guard<std::mutex> lock(response_mutex_);
            responses_.erase(req_copy.header.id);
            lcm_->unsubscribe(subscription);
            throw std::runtime_error("Service call to '" + service_channel_ + "' timed out after " + std::to_string(timeout_seconds) + "s");
        }
        
        ResponseType response = response_future.get();
        lcm_->unsubscribe(subscription);
        return response;
        
    } catch (...) {
        std::lock_guard<std::mutex> lock(response_mutex_);
        responses_.erase(req_copy.header.id);
        lcm_->unsubscribe(subscription);
        throw;
    }
}

template<typename RequestType, typename ResponseType>
void ServiceClient<RequestType, ResponseType>::handle_response(const ResponseType* response) {
    std::lock_guard<std::mutex> lock(response_mutex_);
    auto it = responses_.find(response->response_header.header.id);
    if (it != responses_.end()) {
        if (response->response_header.success) {
            it->second.set_value(*response);
        } else {
            it->second.set_exception(std::make_exception_ptr(
                std::runtime_error(response->response_header.error_message)));
        }
        responses_.erase(it);
    }
}

template<typename RequestType, typename ResponseType>
std::string ServiceClient<RequestType, ResponseType>::generate_client_name() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_int_distribution<> dis(0, 15);
    
    std::string name = "cli_";
    for (int i = 0; i < 5; ++i) {
        name += "0123456789abcdef"[dis(gen)];
    }
    return name;
}

template<typename RequestType, typename ResponseType>
void ServiceClient<RequestType, ResponseType>::verify_client_name(const std::string& name) {
    if (name.length() > MAX_CLIENT_NAME_LENGTH) {
        throw std::invalid_argument("Client name must be " + std::to_string(MAX_CLIENT_NAME_LENGTH) + 
                                   " characters or less, got " + std::to_string(name.length()));
    }
}

// ServiceServer Implementation

template<typename RequestType, typename ResponseType>
ServiceServer<RequestType, ResponseType>::ServiceServer(
    const std::string& service_channel, ServiceHandler handler)
    : service_channel_(service_channel), handler_(handler), 
      subscription_(nullptr), running_(false) {
    
    if (service_channel_.empty()) {
        throw std::invalid_argument("Service channel cannot be empty");
    }
    if (!handler_) {
        throw std::invalid_argument("Handler cannot be null");
    }
    
    lcm_ = getLCM();
    request_handler_ = std::make_unique<RequestHandler>();
    request_handler_->server = this;
}

template<typename RequestType, typename ResponseType>
ServiceServer<RequestType, ResponseType>::~ServiceServer() {
    stop();
}


template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::start() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (running_) {
        return;
    }
    
    try {
        // Subscribe to request channel
        std::string request_channel = service_channel_ + "/req";
        subscription_ = lcm_->subscribe(request_channel, 
            &RequestHandler::handleMessage, request_handler_.get());
        
        running_ = true;
        
        // Ensure LCM handler is running
        startLCMHandler();
        
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to start service server: " + std::string(e.what()));
    }
}

template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::stop() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!running_) {
        return;
    }
    
    try {
        if (subscription_) {
            lcm_->unsubscribe(subscription_);
            subscription_ = nullptr;
        }
        running_ = false;
    } catch (const std::exception& e) {
        // Log error but don't throw
    }
}

template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::spin() {
    start();
    try {
        while (running_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100)); // Wait while LCM handler thread processes messages
        }
    } catch (const std::exception& e) {
        // Handle interruption
    }
    stop();
}

template<typename RequestType, typename ResponseType>
bool ServiceServer<RequestType, ResponseType>::handle_once(int timeout_ms) {
    if (!running_) {
        start();
    }
    return lcm_->handleTimeout(timeout_ms) > 0;
}

template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::handle_request(
    const std::string& channel, const RequestType* request) {
    
    try {
        ResponseType response;
        
        // Call user handler
        try {
            response = handler_(*request);
            response.response_header.success = true;
            response.response_header.error_message = "";
        } catch (const std::exception& e) {
            response.response_header.success = false;
            response.response_header.error_message = e.what();
        }
        
        // Set response header
        auto now = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        response.response_header.header.timestamp_us = now;
        response.response_header.header.id = request->header.id;
        
        // Publish response
        std::string response_channel = service_channel_ + "/rsp/" + request->header.id;
        lcm_->publish(response_channel, &response);
        
    } catch (const std::exception& e) {
        // Log error but continue processing
    }
}

} // namespace lcmware