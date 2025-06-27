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
#include "manager.hpp"

namespace lcmware {

// Forward declaration
template<typename GoalType, typename FeedbackType, typename ResultType>
class ActionClient;

template<typename GoalType, typename FeedbackType, typename ResultType>
class ActionHandle {
public:
    using FeedbackCallback = std::function<void(const FeedbackType&)>;

    /**
     * @brief Initialize action handle
     * @param client Pointer to the action client
     * @param action_channel Full action channel path
     * @param goal_id Unique goal identifier
     */
    ActionHandle(ActionClient<GoalType, FeedbackType, ResultType>* client,
                const std::string& action_channel, const std::string& goal_id);
    
    /**
     * @brief Get the goal ID
     * @return The goal ID
     */
    const std::string& getGoalId() const { return goal_id_; }
    
    /**
     * @brief Get the current status
     * @return The current status
     */
    int getStatus() const { return status_; }
    
    /**
     * @brief Check if the goal was cancelled
     * @return True if cancelled, false otherwise
     */
    bool isCancelled() const { return cancelled_; }

    void add_feedback_callback(FeedbackCallback callback);
    void cancel();
    ResultType get_result(double timeout_seconds = -1.0);
    
    // Internal methods
    void _set_feedback(const FeedbackType& feedback);
    void _set_result(const ResultType& result, int status);

private:
    ActionClient<GoalType, FeedbackType, ResultType>* action_client_;
    std::string action_channel_;
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

    /**
     * @brief Initialize action client for a specific action
     * @param action_channel Full action channel path (e.g., "/robot/move_arm")
     * @param client_name Optional client name (max 16 chars). If empty, generates one.
     */
    ActionClient(const std::string& action_channel, const std::string& client_name = "");
    ~ActionClient();
    
    /**
     * @brief Get the action channel
     * @return The action channel
     */
    const std::string& getActionChannel() const { return action_channel_; }

    void stop();
    
    /**
     * @brief Send an action goal
     * @param goal LCM goal message instance
     * @return ActionHandle for tracking the goal
     */
    ActionHandlePtr send_goal(const GoalType& goal);
    
    void _cancel_goal(const std::string& action_channel, const std::string& goal_id);

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

    std::string action_channel_;
    std::string client_name_;
    std::shared_ptr<lcm::LCM> lcm_;
    std::unordered_map<std::string, ActionHandlePtr> active_goals_;
    std::mutex goals_mutex_;
    int goal_counter_;
    std::vector<lcm::Subscription*> subscriptions_;
    std::unordered_map<std::string, std::unique_ptr<FeedbackHandler>> feedback_handlers_;
    std::unordered_map<std::string, std::unique_ptr<ResultHandler>> result_handlers_;
    
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

    /**
     * @brief Initialize action server for a specific action
     * @param action_channel Full action channel path (e.g., "/robot/move_arm")
     * @param handler Function that takes (goal, feedback_callback) and returns result
     */
    ActionServer(const std::string& action_channel, ActionHandler handler);
    ~ActionServer();
    
    /**
     * @brief Get the action channel
     * @return The action channel
     */
    const std::string& getActionChannel() const { return action_channel_; }
    
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

    std::string action_channel_;
    ActionHandler handler_;
    std::shared_ptr<lcm::LCM> lcm_;
    std::unordered_map<std::string, std::thread> active_goals_;
    std::mutex goals_mutex_;
    lcm::Subscription* goal_subscription_;
    lcm::Subscription* cancel_subscription_;
    std::unique_ptr<GoalHandler> goal_handler_;
    std::unique_ptr<CancelHandler> cancel_handler_;
    std::atomic<bool> running_;
    std::mutex mutex_;
    
    void handle_goal(const std::string& channel, const GoalType* goal);
    void handle_cancel(const std::string& channel, const core::ActionCancel* cancel);
    void execute_action(const GoalType& goal, const std::string& goal_id);
};

// ActionHandle implementation

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionHandle<GoalType, FeedbackType, ResultType>::ActionHandle(
    ActionClient<GoalType, FeedbackType, ResultType>* client,
    const std::string& action_channel, const std::string& goal_id)
    : action_client_(client), action_channel_(action_channel), goal_id_(goal_id),
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
        action_client_->_cancel_goal(action_channel_, goal_id_);
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
    const std::string& action_channel, const std::string& client_name)
    : action_channel_(action_channel), goal_counter_(0) {
    
    if (action_channel_.empty()) {
        throw std::invalid_argument("Action channel cannot be empty");
    }
    
    if (client_name.empty()) {
        client_name_ = generate_client_name();
    } else {
        verify_client_name(client_name);
        client_name_ = client_name;
    }
    
    lcm_ = getLCM();
}

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionClient<GoalType, FeedbackType, ResultType>::~ActionClient() {
    stop();
}


template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::stop() {
    std::lock_guard<std::mutex> lock(goals_mutex_);
    
    for (auto* subscription : subscriptions_) {
        try {
            lcm_->unsubscribe(subscription);
        } catch (...) {
            // Ignore errors during cleanup
        }
    }
    subscriptions_.clear();
    feedback_handlers_.clear();
    result_handlers_.clear();
    active_goals_.clear();
}


template<typename GoalType, typename FeedbackType, typename ResultType>
typename ActionClient<GoalType, FeedbackType, ResultType>::ActionHandlePtr
ActionClient<GoalType, FeedbackType, ResultType>::send_goal(const GoalType& goal) {
    
    // Ensure LCM handler is running
    startLCMHandler();
    
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
        this, action_channel_, goal_id);
    
    {
        std::lock_guard<std::mutex> lock(goals_mutex_);
        active_goals_[goal_id] = handle;
    }
    
    // Subscribe to feedback and result channels
    std::string feedback_channel = action_channel_ + "/fb/" + goal_id;
    std::string result_channel = action_channel_ + "/res/" + goal_id;
    
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
    std::string goal_channel = action_channel_ + "/goal";
    lcm_->publish(goal_channel, &goal_copy);
    
    return handle;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionClient<GoalType, FeedbackType, ResultType>::_cancel_goal(
    const std::string& action_channel, const std::string& goal_id) {
    
    core::ActionCancel cancel_msg;
    auto now = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    cancel_msg.header.timestamp_us = now;
    cancel_msg.header.id = goal_id;
    cancel_msg.goal_id = goal_id;
    
    std::string cancel_channel = action_channel + "/cancel";
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
    const std::string& action_channel, ActionHandler handler)
    : action_channel_(action_channel), handler_(handler), 
      goal_subscription_(nullptr), cancel_subscription_(nullptr), running_(false) {
    
    if (action_channel_.empty()) {
        throw std::invalid_argument("Action channel cannot be empty");
    }
    if (!handler_) {
        throw std::invalid_argument("Handler cannot be null");
    }
    
    lcm_ = getLCM();
    goal_handler_ = std::make_unique<GoalHandler>();
    goal_handler_->server = this;
    cancel_handler_ = std::make_unique<CancelHandler>();
    cancel_handler_->server = this;
}

template<typename GoalType, typename FeedbackType, typename ResultType>
ActionServer<GoalType, FeedbackType, ResultType>::~ActionServer() {
    stop();
}


template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::start() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (running_) {
        return;
    }
    
    try {
        std::string goal_channel = action_channel_ + "/goal";
        std::string cancel_channel = action_channel_ + "/cancel";
        
        goal_subscription_ = lcm_->subscribe(goal_channel,
            &GoalHandler::handleMessage, goal_handler_.get());
        cancel_subscription_ = lcm_->subscribe(cancel_channel,
            &CancelHandler::handleMessage, cancel_handler_.get());
        
        running_ = true;
        
        // Ensure LCM handler is running
        startLCMHandler();
        
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to start action server: " + std::string(e.what()));
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::stop() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!running_) {
        return;
    }
    
    try {
        if (goal_subscription_) {
            lcm_->unsubscribe(goal_subscription_);
            goal_subscription_ = nullptr;
        }
        if (cancel_subscription_) {
            lcm_->unsubscribe(cancel_subscription_);
            cancel_subscription_ = nullptr;
        }
        
        // Wait for active goals to complete (with timeout)
        {
            std::lock_guard<std::mutex> goals_lock(goals_mutex_);
            for (auto& [goal_id, thread] : active_goals_) {
                if (thread.joinable()) {
                    thread.join();
                }
            }
            active_goals_.clear();
        }
        
        running_ = false;
    } catch (const std::exception& e) {
        // Log error but don't throw
    }
}

template<typename GoalType, typename FeedbackType, typename ResultType>
void ActionServer<GoalType, FeedbackType, ResultType>::spin() {
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
    
    try {
        std::string goal_id = goal->header.id;
        
        // Execute action in separate thread
        std::lock_guard<std::mutex> lock(goals_mutex_);
        active_goals_[goal_id] = std::thread(&ActionServer::execute_action, this, *goal, goal_id);
        active_goals_[goal_id].detach();
        
    } catch (const std::exception& e) {
        // Log error but continue processing
    }
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
    const GoalType& goal, const std::string& goal_id) {
    
    // Create feedback callback
    auto send_feedback = [this, goal_id](const FeedbackType& feedback_data) {
        FeedbackType feedback = feedback_data;
        auto now = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        feedback.header.timestamp_us = now;
        feedback.header.id = goal_id;
        
        std::string fb_channel = action_channel_ + "/fb/" + goal_id;
        lcm_->publish(fb_channel, &feedback);
    };
    
    // Execute action
    ResultType result;
    int status;
    std::string error_msg;
    
    try {
        result = handler_(goal, send_feedback);
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
    
    std::string res_channel = action_channel_ + "/res/" + goal_id;
    lcm_->publish(res_channel, &result);
    
    // Clean up
    std::lock_guard<std::mutex> lock(goals_mutex_);
    active_goals_.erase(goal_id);
}

} // namespace lcmware