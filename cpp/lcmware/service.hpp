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

namespace lcmware {

template<typename RequestType, typename ResponseType>
class ServiceClient {
public:
    ServiceClient(const std::string& ns, const std::string& client_name = "", 
                  std::shared_ptr<lcm::LCM> lcm_instance = nullptr);
    ~ServiceClient();

    void start();
    void stop();
    
    ResponseType call(const std::string& service_name, const RequestType& request, 
                     double timeout_seconds = 5.0);

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

    std::string namespace_;
    std::string client_name_;
    std::shared_ptr<lcm::LCM> lcm_;
    std::unordered_map<std::string, std::promise<ResponseType>> responses_;
    std::mutex response_mutex_;
    std::thread handler_thread_;
    std::atomic<bool> running_;
    int request_counter_;
    ResponseHandler response_handler_;
    
    void handle_loop();
    void handle_response(const ResponseType* response);
    std::string generate_client_name();
    void verify_client_name(const std::string& name);
};

template<typename RequestType, typename ResponseType>
class ServiceServer {
public:
    using ServiceHandler = std::function<ResponseType(const RequestType&)>;

    ServiceServer(const std::string& ns, std::shared_ptr<lcm::LCM> lcm_instance = nullptr);
    ~ServiceServer();

    void register_service(const std::string& service_name, ServiceHandler handler);
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

    std::string namespace_;
    std::shared_ptr<lcm::LCM> lcm_;
    std::unordered_map<std::string, ServiceHandler> services_;
    std::vector<lcm::Subscription*> subscriptions_;
    std::vector<std::unique_ptr<RequestHandler>> handlers_;
    std::atomic<bool> running_;
    
    void handle_request(const std::string& channel, const RequestType* request);
};

// ServiceClient Implementation

template<typename RequestType, typename ResponseType>
ServiceClient<RequestType, ResponseType>::ServiceClient(
    const std::string& ns, const std::string& client_name, 
    std::shared_ptr<lcm::LCM> lcm_instance)
    : namespace_(ns), running_(false), request_counter_(0) {
    
    if (client_name.empty()) {
        client_name_ = generate_client_name();
    } else {
        verify_client_name(client_name);
        client_name_ = client_name;
    }
    
    lcm_ = lcm_instance ? lcm_instance : std::make_shared<lcm::LCM>();
    response_handler_.client = this;
}

template<typename RequestType, typename ResponseType>
ServiceClient<RequestType, ResponseType>::~ServiceClient() {
    stop();
}

template<typename RequestType, typename ResponseType>
void ServiceClient<RequestType, ResponseType>::start() {
    if (!running_.exchange(true)) {
        handler_thread_ = std::thread(&ServiceClient::handle_loop, this);
    }
}

template<typename RequestType, typename ResponseType>
void ServiceClient<RequestType, ResponseType>::stop() {
    if (running_.exchange(false)) {
        if (handler_thread_.joinable()) {
            handler_thread_.join();
        }
    }
}

template<typename RequestType, typename ResponseType>
void ServiceClient<RequestType, ResponseType>::handle_loop() {
    while (running_) {
        lcm_->handleTimeout(100); // 100ms timeout
    }
}

template<typename RequestType, typename ResponseType>
ResponseType ServiceClient<RequestType, ResponseType>::call(
    const std::string& service_name, const RequestType& request, double timeout_seconds) {
    
    if (!running_) {
        start();
    }
    
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
    std::string response_channel = "/" + namespace_ + "/svc/" + service_name + "/rsp/" + req_copy.header.id;
    auto subscription = lcm_->subscribe(response_channel, 
        &ResponseHandler::handleMessage, &response_handler_);
    
    // Publish request
    std::string request_channel = "/" + namespace_ + "/svc/" + service_name + "/req";
    lcm_->publish(request_channel, &req_copy);
    
    // Wait for response
    try {
        auto status = response_future.wait_for(std::chrono::duration<double>(timeout_seconds));
        if (status == std::future_status::timeout) {
            std::lock_guard<std::mutex> lock(response_mutex_);
            responses_.erase(req_copy.header.id);
            lcm_->unsubscribe(subscription);
            throw std::runtime_error("Service call timed out after " + std::to_string(timeout_seconds) + "s");
        }
        
        ResponseType response = response_future.get();
        lcm_->unsubscribe(subscription);
        return response;
        
    } catch (...) {
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
    const std::string& ns, std::shared_ptr<lcm::LCM> lcm_instance)
    : namespace_(ns), running_(false) {
    
    lcm_ = lcm_instance ? lcm_instance : std::make_shared<lcm::LCM>();
}

template<typename RequestType, typename ResponseType>
ServiceServer<RequestType, ResponseType>::~ServiceServer() {
    stop();
}

template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::register_service(
    const std::string& service_name, ServiceHandler handler) {
    
    if (running_) {
        throw std::runtime_error("Cannot register service while server is running");
    }
    services_[service_name] = handler;
}

template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::start() {
    if (running_) {
        return;
    }
    
    for (const auto& [service_name, handler] : services_) {
        std::string request_channel = "/" + namespace_ + "/svc/" + service_name + "/req";
        
        auto req_handler = std::make_unique<RequestHandler>();
        req_handler->server = this;
        req_handler->service_name = service_name;
        
        auto subscription = lcm_->subscribe(request_channel, 
            &RequestHandler::handleMessage, req_handler.get());
        subscriptions_.push_back(subscription);
        handlers_.push_back(std::move(req_handler));
    }
    
    running_ = true;
}

template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::stop() {
    if (!running_) {
        return;
    }
    
    for (auto* subscription : subscriptions_) {
        lcm_->unsubscribe(subscription);
    }
    subscriptions_.clear();
    handlers_.clear();
    running_ = false;
}

template<typename RequestType, typename ResponseType>
void ServiceServer<RequestType, ResponseType>::spin() {
    start();
    try {
        while (true) {
            lcm_->handle();
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
    
    // Extract service name from channel
    // Channel format: /{namespace}/svc/{service_name}/req
    std::string prefix = "/" + namespace_ + "/svc/";
    std::string suffix = "/req";
    
    if (channel.substr(0, prefix.length()) != prefix || 
        channel.substr(channel.length() - suffix.length()) != suffix) {
        return;
    }
    
    std::string service_name = channel.substr(prefix.length(), 
        channel.length() - prefix.length() - suffix.length());
    
    auto it = services_.find(service_name);
    if (it == services_.end()) {
        return;
    }
    
    ResponseType response;
    try {
        response = it->second(*request);
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
    std::string response_channel = "/" + namespace_ + "/svc/" + service_name + "/rsp/" + request->header.id;
    lcm_->publish(response_channel, &response);
}

} // namespace lcmware