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
#include <vector>
#include <random>
#include "constants.hpp"
#include "types/core/ActionCancel.hpp"

namespace lcmware {

// Forward declaration
template<typename GoalType, typename FeedbackType, typename ResultType>
class ActionClient;

template<typename GoalType, typename FeedbackType, typename ResultType>
class ActionHandle {
public:
    using FeedbackCallback = std::function<void(const FeedbackType&)>;

    ActionHandle(ActionClient<GoalType, FeedbackType, ResultType>* client,
                const std::string& action_name, const std::string& goal_id);

    void add_feedback_callback(FeedbackCallback callback);
    void cancel();
    ResultType get_result(double timeout_seconds = -1.0);
    
    // Internal methods
    void _set_feedback(const FeedbackType& feedback);
    void _set_result(const ResultType& result, int status);

private:
    ActionClient<GoalType, FeedbackType, ResultType>* action_client_;
    std::string action_name_;
    std::string goal_id_;
    std::promise<ResultType> result_promise_;
    std::vector<FeedbackCallback> feedback_callbacks_;
    std::atomic<int> status_;
    std::atomic<bool> cancelled_;
};

template<typename GoalType, typename FeedbackType, typename ResultType>
class ActionClient {
public:
    using ActionHandlePtr = std::shared_ptr<ActionHandle<GoalType, FeedbackType, ResultType>>;

    ActionClient(const std::string& ns, const std::string& client_name = "",
                std::shared_ptr<lcm::LCM> lcm_instance = nullptr);
    ~ActionClient();

    void start();
    void stop();
    
    ActionHandlePtr send_goal(const std::string& action_name, const GoalType& goal);
    void _cancel_goal(const std::string& action_name, const std::string& goal_id);

private:
    class FeedbackHandler {
    public:
        ActionClient* client;
        
        void handleMessage(const lcm::ReceiveBuffer* rbuf,
                          const std::string& chan,
                          const FeedbackType* msg) {
            client->handle_feedback(msg);
        }
    };
    
    class ResultHandler {
    public:
        ActionClient* client;
        
        void handleMessage(const lcm::ReceiveBuffer* rbuf,
                          const std::string& chan,
                          const ResultType* msg) {
            client->handle_result(msg);
        }
    };

    std::string namespace_;
    std::string client_name_;
    std::shared_ptr<lcm::LCM> lcm_;
    std::unordered_map<std::string, ActionHandlePtr> active_goals_;
    std::mutex goals_mutex_;
    std::thread handler_thread_;
    std::atomic<bool> running_;
    int goal_counter_;
    std::vector<lcm::Subscription*> subscriptions_;
    std::unordered_map<std::string, std::unique_ptr<FeedbackHandler>> feedback_handlers_;
    std::unordered_map<std::string, std::unique_ptr<ResultHandler>> result_handlers_;
    
    void handle_loop();
    void handle_feedback(const FeedbackType* feedback);
    void handle_result(const ResultType* result);
    std::string generate_client_name();
    void verify_client_name(const std::string& name);
};

template<typename GoalType, typename FeedbackType, typename ResultType>
class ActionServer {
public:
    using FeedbackCallback = std::function<void(const FeedbackType&)>;
    using ActionHandler = std::function<ResultType(const GoalType&, FeedbackCallback)>;

    ActionServer(const std::string& ns, std::shared_ptr<lcm::LCM> lcm_instance = nullptr);
    ~ActionServer();

    void register_action(const std::string& action_name, ActionHandler handler);
    void start();
    void stop();
    void spin();
    bool handle_once(int timeout_ms = 0);

private:
    class GoalHandler {
    public:
        ActionServer* server;
        std::string action_name;
        
        void handleMessage(const lcm::ReceiveBuffer* rbuf,
                          const std::string& chan,
                          const GoalType* msg) {
            server->handle_goal(chan, msg);
        }
    };
    
    class CancelHandler {
    public:
        ActionServer* server;
        std::string action_name;
        
        void handleMessage(const lcm::ReceiveBuffer* rbuf,
                          const std::string& chan,
                          const core::ActionCancel* msg) {
            server->handle_cancel(chan, msg);
        }
    };

    std::string namespace_;
    std::shared_ptr<lcm::LCM> lcm_;
    std::unordered_map<std::string, ActionHandler> actions_;
    std::unordered_map<std::string, std::thread> active_goals_;
    std::mutex goals_mutex_;
    std::vector<lcm::Subscription*> subscriptions_;
    std::vector<std::unique_ptr<GoalHandler>> goal_handlers_;
    std::vector<std::unique_ptr<CancelHandler>> cancel_handlers_;
    std::atomic<bool> running_;
    
    void handle_goal(const std::string& channel, const GoalType* goal);
    void handle_cancel(const std::string& channel, const core::ActionCancel* cancel);
    void execute_action(const std::string& action_name, const GoalType& goal, 
                       const std::string& goal_id, ActionHandler handler);
};

// ActionHandle implementation

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionHandle<GoalType, FeedbackType, ResultType>::ActionHandle(
    ActionClient<GoalType, FeedbackType, ResultType>* client,
    const std::string& action_name, const std::string& goal_id)
    : action_client_(client), action_name_(action_name), goal_id_(goal_id),
      status_(static_cast<int>(ActionStatus::ACCEPTED)), cancelled_(false) {
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionHandle<GoalType, FeedbackType, ResultType>::add_feedback_callback(FeedbackCallback callback) {
    feedback_callbacks_.push_back(callback);
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionHandle<GoalType, FeedbackType, ResultType>::cancel() {
    if (!cancelled_.exchange(true) && 
        (status_ == static_cast<int>(ActionStatus::ACCEPTED) || status_ == static_cast<int>(ActionStatus::EXECUTING))) {
        action_client_->_cancel_goal(action_name_, goal_id_);
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
ResultType ActionHandle<GoalType, FeedbackType, ResultType>::get_result(double timeout_seconds) {
    auto future = result_promise_.get_future();
    if (timeout_seconds < 0) {
        return future.get();
    } else {
        auto status = future.wait_for(std::chrono::duration<double>(timeout_seconds));
        if (status == std::future_status::timeout) {
            throw std::runtime_error("Action result timed out");
        }
        return future.get();
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionHandle<GoalType, FeedbackType, ResultType>::_set_feedback(const FeedbackType& feedback) {
    for (auto& callback : feedback_callbacks_) {
        try {
            callback(feedback);
        } catch (const std::exception& e) {
            // Log error but continue
        }
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionHandle<GoalType, FeedbackType, ResultType>::_set_result(const ResultType& result, int status) {
    status_ = status;
    if (status == static_cast<int>(ActionStatus::SUCCEEDED)) {
        result_promise_.set_value(result);
    } else {
        result_promise_.set_exception(std::make_exception_ptr(
            std::runtime_error("Action failed with status " + std::to_string(status))));
    }
}

// ActionClient implementation

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionClient<GoalType, FeedbackType, ResultType>::ActionClient(
    const std::string& ns, const std::string& client_name,
    std::shared_ptr<lcm::LCM> lcm_instance)
    : namespace_(ns), running_(false), goal_counter_(0) {
    
    if (client_name.empty()) {
        client_name_ = generate_client_name();
    } else {
        verify_client_name(client_name);
        client_name_ = client_name;
    }
    
    lcm_ = lcm_instance ? lcm_instance : std::make_shared<lcm::LCM>();
}

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionClient<GoalType, FeedbackType, ResultType>::~ActionClient() {
    stop();
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::start() {
    if (!running_.exchange(true)) {
        handler_thread_ = std::thread(&ActionClient::handle_loop, this);
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::stop() {
    if (running_.exchange(false)) {
        if (handler_thread_.joinable()) {
            handler_thread_.join();
        }
        
        for (auto* subscription : subscriptions_) {
            lcm_->unsubscribe(subscription);
        }
        subscriptions_.clear();
        feedback_handlers_.clear();
        result_handlers_.clear();
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::handle_loop() {
    while (running_) {
        lcm_->handleTimeout(100);
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
typename ActionClient<GoalType, FeedbackType, ResultType>::ActionHandlePtr
ActionClient<GoalType, FeedbackType, ResultType>::send_goal(
    const std::string& action_name, const GoalType& goal) {
    
    if (!running_) {
        start();
    }
    
    // Generate unique goal ID
    std::string goal_id = client_name_ + "_" + std::to_string(++goal_counter_);
    
    // Create goal message
    GoalType goal_copy = goal;
    auto now = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    goal_copy.header.timestamp_us = now;
    goal_copy.header.id = goal_id;
    
    // Create action handle
    auto handle = std::make_shared<ActionHandle<GoalType, FeedbackType, ResultType>>(
        this, action_name, goal_id);
    
    {
        std::lock_guard<std::mutex> lock(goals_mutex_);
        active_goals_[goal_id] = handle;
    }
    
    // Subscribe to feedback and result channels
    std::string feedback_channel = "/" + namespace_ + "/act/" + action_name + "/fb/" + goal_id;
    std::string result_channel = "/" + namespace_ + "/act/" + action_name + "/res/" + goal_id;
    
    auto fb_handler = std::make_unique<FeedbackHandler>();
    fb_handler->client = this;
    auto res_handler = std::make_unique<ResultHandler>();
    res_handler->client = this;
    
    auto fb_sub = lcm_->subscribe(feedback_channel, 
        &FeedbackHandler::handleMessage, fb_handler.get());
    auto res_sub = lcm_->subscribe(result_channel, 
        &ResultHandler::handleMessage, res_handler.get());
    
    subscriptions_.push_back(fb_sub);
    subscriptions_.push_back(res_sub);
    feedback_handlers_[goal_id] = std::move(fb_handler);
    result_handlers_[goal_id] = std::move(res_handler);
    
    // Publish goal
    std::string goal_channel = "/" + namespace_ + "/act/" + action_name + "/goal";
    lcm_->publish(goal_channel, &goal_copy);
    
    return handle;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::_cancel_goal(
    const std::string& action_name, const std::string& goal_id) {
    
    core::ActionCancel cancel_msg;
    auto now = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    cancel_msg.header.timestamp_us = now;
    cancel_msg.header.id = goal_id;
    cancel_msg.goal_id = goal_id;
    
    std::string cancel_channel = "/" + namespace_ + "/act/" + action_name + "/cancel";
    lcm_->publish(cancel_channel, &cancel_msg);
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::handle_feedback(const FeedbackType* feedback) {
    std::lock_guard<std::mutex> lock(goals_mutex_);
    auto it = active_goals_.find(feedback->header.id);
    if (it != active_goals_.end()) {
        it->second->_set_feedback(*feedback);
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::handle_result(const ResultType* result) {
    std::lock_guard<std::mutex> lock(goals_mutex_);
    std::string goal_id = result->status.header.id;
    auto it = active_goals_.find(goal_id);
    if (it != active_goals_.end()) {
        auto handle = it->second;
        active_goals_.erase(it);
        handle->_set_result(*result, result->status.status);
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
std::string ActionClient<GoalType, FeedbackType, ResultType>::generate_client_name() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_int_distribution<> dis(0, 15);
    
    std::string name = "act_";
    for (int i = 0; i < 5; ++i) {
        name += "0123456789abcdef"[dis(gen)];
    }
    return name;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::verify_client_name(const std::string& name) {
    if (name.length() > MAX_CLIENT_NAME_LENGTH) {
        throw std::invalid_argument("Client name must be " + std::to_string(MAX_CLIENT_NAME_LENGTH) + 
                                   " characters or less, got " + std::to_string(name.length()));
    }
}

// ActionServer implementation

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionServer<GoalType, FeedbackType, ResultType>::ActionServer(
    const std::string& ns, std::shared_ptr<lcm::LCM> lcm_instance)
    : namespace_(ns), running_(false) {
    
    lcm_ = lcm_instance ? lcm_instance : std::make_shared<lcm::LCM>();
}

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionServer<GoalType, FeedbackType, ResultType>::~ActionServer() {
    stop();
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::register_action(
    const std::string& action_name, ActionHandler handler) {
    
    if (running_) {
        throw std::runtime_error("Cannot register action while server is running");
    }
    actions_[action_name] = handler;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::start() {
    if (running_) {
        return;
    }
    
    for (const auto& [action_name, handler] : actions_) {
        std::string goal_channel = "/" + namespace_ + "/act/" + action_name + "/goal";
        std::string cancel_channel = "/" + namespace_ + "/act/" + action_name + "/cancel";
        
        auto goal_handler = std::make_unique<GoalHandler>();
        goal_handler->server = this;
        goal_handler->action_name = action_name;
        
        auto cancel_handler = std::make_unique<CancelHandler>();
        cancel_handler->server = this;
        cancel_handler->action_name = action_name;
        
        auto goal_sub = lcm_->subscribe(goal_channel,
            &GoalHandler::handleMessage, goal_handler.get());
        auto cancel_sub = lcm_->subscribe(cancel_channel,
            &CancelHandler::handleMessage, cancel_handler.get());
            
        subscriptions_.push_back(goal_sub);
        subscriptions_.push_back(cancel_sub);
        goal_handlers_.push_back(std::move(goal_handler));
        cancel_handlers_.push_back(std::move(cancel_handler));
    }
    
    running_ = true;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::stop() {
    if (!running_) {
        return;
    }
    
    for (auto* subscription : subscriptions_) {
        lcm_->unsubscribe(subscription);
    }
    subscriptions_.clear();
    goal_handlers_.clear();
    cancel_handlers_.clear();
    
    // Wait for active goals to complete
    std::lock_guard<std::mutex> lock(goals_mutex_);
    for (auto& [goal_id, thread] : active_goals_) {
        if (thread.joinable()) {
            thread.join();
        }
    }
    active_goals_.clear();
    
    running_ = false;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::spin() {
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

template<typename GoalType, typename FeedbackType, typename ResultType>
bool ActionServer<GoalType, FeedbackType, ResultType>::handle_once(int timeout_ms) {
    if (!running_) {
        start();
    }
    return lcm_->handleTimeout(timeout_ms) > 0;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::handle_goal(
    const std::string& channel, const GoalType* goal) {
    
    // Extract action name from channel
    std::string prefix = "/" + namespace_ + "/act/";
    std::string suffix = "/goal";
    
    if (channel.substr(0, prefix.length()) != prefix || 
        channel.substr(channel.length() - suffix.length()) != suffix) {
        return;
    }
    
    std::string action_name = channel.substr(prefix.length(), 
        channel.length() - prefix.length() - suffix.length());
    
    auto it = actions_.find(action_name);
    if (it == actions_.end()) {
        return;
    }
    
    std::string goal_id = goal->header.id;
    
    // Execute action in separate thread
    std::lock_guard<std::mutex> lock(goals_mutex_);
    active_goals_[goal_id] = std::thread(&ActionServer::execute_action, this,
        action_name, *goal, goal_id, it->second);
    active_goals_[goal_id].detach();
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::handle_cancel(
    const std::string& channel, const core::ActionCancel* cancel) {
    
    std::string goal_id = cancel->goal_id;
    
    std::lock_guard<std::mutex> lock(goals_mutex_);
    auto it = active_goals_.find(goal_id);
    if (it != active_goals_.end()) {
        // Note: Can't actually stop the thread, would need cooperative cancellation
        active_goals_.erase(it);
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::execute_action(
    const std::string& action_name, const GoalType& goal, 
    const std::string& goal_id, ActionHandler handler) {
    
    // Create feedback callback
    auto send_feedback = [this, action_name, goal_id](const FeedbackType& feedback_data) {
        FeedbackType feedback = feedback_data;
        auto now = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        feedback.header.timestamp_us = now;
        feedback.header.id = goal_id;
        
        std::string fb_channel = "/" + namespace_ + "/act/" + action_name + "/fb/" + goal_id;
        lcm_->publish(fb_channel, &feedback);
    };
    
    // Execute action
    ResultType result;
    int status;
    std::string error_msg;
    
    try {
        result = handler(goal, send_feedback);
        status = static_cast<int>(ActionStatus::SUCCEEDED);
        error_msg = "";
    } catch (const std::exception& e) {
        status = static_cast<int>(ActionStatus::ABORTED);
        error_msg = e.what();
    }
    
    // Send result
    auto now = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    result.status.header.timestamp_us = now;
    result.status.header.id = goal_id;
    result.status.status = status;
    result.status.message = error_msg;
    
    std::string res_channel = "/" + namespace_ + "/act/" + action_name + "/res/" + goal_id;
    lcm_->publish(res_channel, &result);
    
    // Clean up
    std::lock_guard<std::mutex> lock(goals_mutex_);
    active_goals_.erase(goal_id);
}

} // namespace lcmware