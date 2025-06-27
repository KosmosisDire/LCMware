#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <lcmware/action.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryGoal.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryFeedback.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryResult.hpp>
#include <lcmware/types/examples/JointTrajectoryPoint.hpp>

using namespace lcmware;

void run_server() {
    std::cout << "Starting action server..." << std::endl;
    
    // Define action handler
    auto trajectory_handler = [](const examples::FollowJointTrajectoryGoal& goal,
                                std::function<void(const examples::FollowJointTrajectoryFeedback&)> send_feedback) 
                                -> examples::FollowJointTrajectoryResult {
        std::cout << "Executing trajectory with " << goal.num_points << " points" << std::endl;
        
        // Simulate trajectory execution
        for (int32_t i = 0; i < goal.num_points; ++i) {
            // Send feedback
            double progress = static_cast<double>(i + 1) / goal.num_points;
            
            examples::FollowJointTrajectoryFeedback feedback;
            feedback.progress = progress;
            feedback.current_point = i;
            feedback.error = 0.01 * (i + 1);  // Simulate increasing error
            
            send_feedback(feedback);
            
            std::cout << "Executing point " << (i+1) << "/" << goal.num_points 
                     << " (progress: " << (progress * 100) << "%)" << std::endl;
            
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        
        // Return result
        examples::FollowJointTrajectoryResult result;
        result.final_error = 0.001;
        result.execution_time = goal.num_points * 0.5;
        
        return result;
    };
    
    // Create server for specific action channel with handler
    ActionServer<examples::FollowJointTrajectoryGoal, 
                 examples::FollowJointTrajectoryFeedback,
                 examples::FollowJointTrajectoryResult> server(
                     "/demo_robot/follow_trajectory", trajectory_handler);
    
    // Run server
    server.spin();
}

void run_client() {
    std::cout << "Starting action client..." << std::endl;
    
    // Create client for specific action channel
    ActionClient<examples::FollowJointTrajectoryGoal,
                 examples::FollowJointTrajectoryFeedback,
                 examples::FollowJointTrajectoryResult> client(
                     "/demo_robot/follow_trajectory", "cpp_traj_cli");
    
    try {
        // Create trajectory goal
        examples::FollowJointTrajectoryGoal goal;
        goal.num_joints = 6;
        goal.joint_names = {"joint1", "joint2", "joint3", "joint4", "joint5", "joint6"};
        
        // Create trajectory points
        std::vector<examples::JointTrajectoryPoint> points;
        for (int i = 0; i < 50; ++i) {
            examples::JointTrajectoryPoint point;
            point.num_positions = 6;
            point.positions.resize(6, i * 0.1);
            point.velocities.resize(6, 0.0);
            point.accelerations.resize(6, 0.0);
            point.time_from_start = static_cast<double>(i + 1);
            points.push_back(point);
        }
        
        goal.num_points = points.size();
        goal.points = points;
        
        std::cout << "Sending trajectory goal..." << std::endl;
        
        // Send goal with typed object
        auto handle = client.send_goal(goal);
        
        // Add feedback callback
        handle->add_feedback_callback([](const examples::FollowJointTrajectoryFeedback& feedback) {
            std::cout << "Progress: " << (feedback.progress * 100) << "%, "
                     << "Point: " << feedback.current_point << ", "
                     << "Error: " << feedback.error << std::endl;
        });
        
        // Wait for result
        std::cout << "Waiting for trajectory completion..." << std::endl;
        auto result = handle->get_result(10.0);
        
        std::cout << "Trajectory completed! Final error: " << result.final_error 
                 << ", Time: " << result.execution_time << "s" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Action failed: " << e.what() << std::endl;
    }
}

void run_client_with_cancel() {
    std::cout << "Starting action client with cancellation..." << std::endl;
    
    // Create client for specific action channel
    ActionClient<examples::FollowJointTrajectoryGoal,
                 examples::FollowJointTrajectoryFeedback,
                 examples::FollowJointTrajectoryResult> client(
                     "/demo_robot/follow_trajectory", "cpp_cancel_cli");
    
    try {
        // Create trajectory goal
        examples::FollowJointTrajectoryGoal goal;
        goal.num_joints = 6;
        goal.joint_names = {"joint1", "joint2", "joint3", "joint4", "joint5", "joint6"};
        
        // Create longer trajectory
        std::vector<examples::JointTrajectoryPoint> points;
        for (int i = 0; i < 10; ++i) {
            examples::JointTrajectoryPoint point;
            point.num_positions = 6;
            point.positions.resize(6, i * 0.1);
            point.velocities.resize(6, 0.0);
            point.accelerations.resize(6, 0.0);
            point.time_from_start = static_cast<double>(i + 1);
            points.push_back(point);
        }
        
        goal.num_points = points.size();
        goal.points = points;
        
        std::cout << "Sending trajectory goal that will be cancelled..." << std::endl;
        
        // Send goal with typed object
        auto handle = client.send_goal(goal);
        
        // Add feedback callback that cancels after 50%
        handle->add_feedback_callback([&handle](const examples::FollowJointTrajectoryFeedback& feedback) {
            std::cout << "Progress: " << (feedback.progress * 100) << "%, "
                     << "Point: " << feedback.current_point << std::endl;
            
            if (feedback.progress > 0.5) {
                std::cout << "Cancelling action..." << std::endl;
                handle->cancel();
            }
        });
        
        // Wait for result (should be cancelled)
        try {
            auto result = handle->get_result(10.0);
            std::cout << "Action completed unexpectedly" << std::endl;
        } catch (const std::exception& e) {
            std::cout << "Action cancelled as expected: " << e.what() << std::endl;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Unexpected error: " << e.what() << std::endl;
    }
}

int main(int argc, char* argv[]) {
    if (argc != 2 || (std::string(argv[1]) != "server" && 
                     std::string(argv[1]) != "client" && 
                     std::string(argv[1]) != "cancel")) {
        std::cerr << "Usage: " << argv[0] << " [server|client|cancel]" << std::endl;
        std::cerr << "" << std::endl;
        std::cerr << "This example demonstrates the new type-safe LCMware C++ action API:" << std::endl;
        std::cerr << "- ActionClient and ActionServer are bound to specific channels and types" << std::endl;
        std::cerr << "- No more generic calls - use typed LCM objects directly" << std::endl;
        std::cerr << "- Feedback and results are fully type-safe" << std::endl;
        std::cerr << "- Single shared LCM instance managed automatically" << std::endl;
        return 1;
    }
    
    std::string mode = argv[1];
    
    if (mode == "server") {
        run_server();
    } else if (mode == "client") {
        run_client();
    } else {  // cancel
        run_client_with_cancel();
    }
    
    return 0;
}