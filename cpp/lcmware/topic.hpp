#pragma once

#include <lcm/lcm-cpp.hpp>
#include <memory>
#include <string>
#include <functional>
#include <stdexcept>
#include "manager.hpp"

namespace lcmware {

/**
 * @brief Type-safe publisher for a single LCM topic
 * @tparam MessageType The LCM message type to publish
 */
template<typename MessageType>
class TopicPublisher {
public:
    /**
     * @brief Initialize topic publisher
     * @param channel Full LCM channel name (e.g., "/robot/sensors/camera")
     */
    explicit TopicPublisher(const std::string& channel);
    
    /**
     * @brief Get the channel name
     * @return The channel name
     */
    const std::string& getChannel() const { return channel_; }
    
    /**
     * @brief Publish a message to the topic
     * @param message LCM message instance of the correct type
     * @return 0 on success, -1 on failure
     */
    int publish(const MessageType& message);

private:
    std::string channel_;
    std::shared_ptr<lcm::LCM> lcm_;
};

/**
 * @brief Type-safe subscriber for a single LCM topic
 * @tparam MessageType The LCM message type to receive
 */
template<typename MessageType>
class TopicSubscriber {
public:
    using CallbackFunction = std::function<void(const MessageType&)>;
    
    /**
     * @brief Initialize topic subscriber
     * @param channel Full LCM channel name (e.g., "/robot/sensors/camera")
     * @param callback Function to call when messages are received
     */
    TopicSubscriber(const std::string& channel, CallbackFunction callback);
    
    /**
     * @brief Destructor - automatically unsubscribes
     */
    ~TopicSubscriber();
    
    /**
     * @brief Get the channel name
     * @return The channel name
     */
    const std::string& getChannel() const { return channel_; }
    
    /**
     * @brief Check if currently subscribed
     * @return True if subscribed, false otherwise
     */
    bool isSubscribed() const { return subscribed_; }
    
    /**
     * @brief Subscribe to the topic
     */
    void subscribe();
    
    /**
     * @brief Unsubscribe from the topic
     */
    void unsubscribe();

private:
    class MessageHandler {
    public:
        TopicSubscriber* subscriber;
        
        void handleMessage(const lcm::ReceiveBuffer* rbuf,
                          const std::string& channel,
                          const MessageType* msg) {
            subscriber->handleMessage(msg);
        }
    };
    
    void handleMessage(const MessageType* message);
    
    std::string channel_;
    CallbackFunction callback_;
    std::shared_ptr<lcm::LCM> lcm_;
    lcm::Subscription* subscription_;
    bool subscribed_;
    std::unique_ptr<MessageHandler> handler_;
};

// TopicPublisher Implementation

template<typename MessageType>
TopicPublisher<MessageType>::TopicPublisher(const std::string& channel)
    : channel_(channel), lcm_(getLCM()) {
    
    if (channel_.empty()) {
        throw std::invalid_argument("Channel cannot be empty");
    }
}

template<typename MessageType>
int TopicPublisher<MessageType>::publish(const MessageType& message) {
    try {
        return lcm_->publish(channel_, &message);
    } catch (const std::exception& e) {
        return -1;
    }
}

// TopicSubscriber Implementation

template<typename MessageType>
TopicSubscriber<MessageType>::TopicSubscriber(const std::string& channel, CallbackFunction callback)
    : channel_(channel), callback_(callback), lcm_(getLCM()), 
      subscription_(nullptr), subscribed_(false) {
    
    if (channel_.empty()) {
        throw std::invalid_argument("Channel cannot be empty");
    }
    if (!callback_) {
        throw std::invalid_argument("Callback cannot be null");
    }
    
    handler_ = std::make_unique<MessageHandler>();
    handler_->subscriber = this;
    
    // Auto-subscribe on creation
    subscribe();
}

template<typename MessageType>
TopicSubscriber<MessageType>::~TopicSubscriber() {
    unsubscribe();
}

template<typename MessageType>
void TopicSubscriber<MessageType>::subscribe() {
    if (subscribed_) {
        return;
    }
    
    try {
        subscription_ = lcm_->subscribe(channel_, 
            &MessageHandler::handleMessage, handler_.get());
        subscribed_ = true;
        
        // Ensure handler thread is running
        startLCMHandler();
        
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to subscribe to channel '" + channel_ + "': " + e.what());
    }
}

template<typename MessageType>
void TopicSubscriber<MessageType>::unsubscribe() {
    if (!subscribed_) {
        return;
    }
    
    try {
        if (subscription_) {
            lcm_->unsubscribe(subscription_);
            subscription_ = nullptr;
        }
        subscribed_ = false;
    } catch (const std::exception& e) {
        // Log error but don't throw in destructor context
    }
}

template<typename MessageType>
void TopicSubscriber<MessageType>::handleMessage(const MessageType* message) {
    try {
        if (callback_ && message) {
            callback_(*message);
        }
    } catch (const std::exception& e) {
        // Log error but continue processing
    }
}

} // namespace lcmware