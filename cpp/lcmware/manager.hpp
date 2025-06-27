#pragma once

#include <lcm/lcm-cpp.hpp>
#include <memory>
#include <mutex>
#include <thread>
#include <atomic>

namespace lcmware {

/**
 * @brief Singleton manager for LCM instance to ensure single shared instance across all clients/servers
 */
class LCMManager {
public:
    /**
     * @brief Get the singleton instance
     * @return Reference to the LCMManager instance
     */
    static LCMManager& getInstance();
    
    /**
     * @brief Get the shared LCM instance
     * @return Shared pointer to the LCM instance
     */
    std::shared_ptr<lcm::LCM> getLCM();
    
    /**
     * @brief Start a background thread for handling LCM messages if not already running
     */
    void startHandlerThread();
    
    /**
     * @brief Stop all handler threads
     */
    void stopHandlerThreads();
    
    /**
     * @brief Shutdown the LCM manager and cleanup resources
     */
    void shutdown();
    
    // Delete copy constructor and assignment operator for singleton
    LCMManager(const LCMManager&) = delete;
    LCMManager& operator=(const LCMManager&) = delete;
    
    /**
     * @brief Destructor (public for unique_ptr compatibility)
     */
    ~LCMManager();

private:
    LCMManager();
    
    void handleLoop();
    
    static std::unique_ptr<LCMManager> instance_;
    static std::mutex instance_mutex_;
    
    std::shared_ptr<lcm::LCM> lcm_;
    std::thread handler_thread_;
    std::atomic<bool> running_;
    std::mutex handler_mutex_;
};

/**
 * @brief Convenience function to get the shared LCM instance
 * @return Shared pointer to the LCM instance
 */
std::shared_ptr<lcm::LCM> getLCM();

/**
 * @brief Convenience function to start the LCM handler thread
 */
void startLCMHandler();

/**
 * @brief Convenience function to stop LCM handler threads
 */
void stopLCMHandler();

// Implementation

std::unique_ptr<LCMManager> LCMManager::instance_ = nullptr;
std::mutex LCMManager::instance_mutex_;

LCMManager& LCMManager::getInstance() {
    std::lock_guard<std::mutex> lock(instance_mutex_);
    if (!instance_) {
        instance_ = std::unique_ptr<LCMManager>(new LCMManager());
    }
    return *instance_;
}

LCMManager::LCMManager() : running_(false) {
    lcm_ = std::make_shared<lcm::LCM>();
    if (!lcm_->good()) {
        throw std::runtime_error("Failed to initialize LCM");
    }
}

LCMManager::~LCMManager() {
    shutdown();
}

std::shared_ptr<lcm::LCM> LCMManager::getLCM() {
    return lcm_;
}

void LCMManager::startHandlerThread() {
    std::lock_guard<std::mutex> lock(handler_mutex_);
    if (!running_.exchange(true)) {
        handler_thread_ = std::thread(&LCMManager::handleLoop, this);
    }
}

void LCMManager::stopHandlerThreads() {
    std::lock_guard<std::mutex> lock(handler_mutex_);
    if (running_.exchange(false)) {
        if (handler_thread_.joinable()) {
            handler_thread_.join();
        }
    }
}

void LCMManager::handleLoop() {
    while (running_) {
        int status = lcm_->handleTimeout(100); // 100ms timeout
        if (status < 0) {
            // Error occurred, but continue trying
            continue;
        }
    }
}

void LCMManager::shutdown() {
    stopHandlerThreads();
    
    // Reset the singleton instance
    std::lock_guard<std::mutex> lock(instance_mutex_);
    instance_.reset();
}

// Convenience functions
std::shared_ptr<lcm::LCM> getLCM() {
    return LCMManager::getInstance().getLCM();
}

void startLCMHandler() {
    LCMManager::getInstance().startHandlerThread();
}

void stopLCMHandler() {
    LCMManager::getInstance().stopHandlerThreads();
}

} // namespace lcmware