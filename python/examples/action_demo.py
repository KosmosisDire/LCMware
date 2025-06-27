#!/usr/bin/env python3
"""Example demonstrating LCMware action usage with new type-safe API"""

import sys
import time
import logging

from lcmware.types.examples import (
    FollowJointTrajectoryGoal, 
    FollowJointTrajectoryFeedback,
    FollowJointTrajectoryResult,
    JointTrajectoryPoint
)
from lcmware import ActionClient, ActionServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_server():
    """Run the action server"""
    def trajectory_handler(goal: FollowJointTrajectoryGoal, send_feedback) -> FollowJointTrajectoryResult:
        """Execute a joint trajectory"""
        logger.info(f"Executing trajectory with {goal.num_points} points")
        
        # Simulate trajectory execution
        for i in range(goal.num_points):
            # Check if we should continue (simplified cancellation check)
            if i >= goal.num_points:
                break
                
            # Create and send feedback
            feedback = FollowJointTrajectoryFeedback()
            feedback.current_point = i
            feedback.error = 0.01 * (i + 1)  # Simulate increasing error
            feedback.progress = (i + 1) / goal.num_points
            send_feedback(feedback)
            
            logger.info(f"Executing point {i+1}/{goal.num_points} (progress: {feedback.progress:.1%})")
            time.sleep(0.05)  # Simulate execution time
        
        # Create and return result
        result = FollowJointTrajectoryResult()
        result.final_error = 0.001
        result.execution_time = goal.num_points * 0.5
        return result
    
    # Create server for specific action channel
    server = ActionServer(
        "/demo_robot/follow_trajectory",
        FollowJointTrajectoryGoal,
        FollowJointTrajectoryFeedback, 
        FollowJointTrajectoryResult,
        trajectory_handler
    )
    
    logger.info("Starting action server...")
    server.spin()


def run_client():
    """Run the action client"""
    # Create client for specific action channel
    client = ActionClient(
        "/demo_robot/follow_trajectory",
        FollowJointTrajectoryGoal,
        FollowJointTrajectoryFeedback,
        FollowJointTrajectoryResult,
        "traj_client"
    )
    
    logger.info("Sending trajectory goal...")
    
    try:
        # Create some trajectory points
        points = []
        for i in range(50):
            point = JointTrajectoryPoint()
            point.num_positions = 6
            point.positions = [float(i) * 0.1] * 6  # Simple trajectory
            point.velocities = [0.0] * 6
            point.accelerations = [0.0] * 6  
            point.time_from_start = float(i + 1)
            points.append(point)
        
        # Create goal object
        goal = FollowJointTrajectoryGoal()
        goal.num_joints = 6
        goal.joint_names = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
        goal.num_points = len(points)
        goal.points = points
        
        # Send goal with typed object
        handle = client.send_goal(goal)
        
        # Add feedback callback
        def on_feedback(feedback: FollowJointTrajectoryFeedback):
            logger.info(f"Progress: {feedback.progress:.1%}, Point: {feedback.current_point}, Error: {feedback.error:.3f}")
        
        handle.add_feedback_callback(on_feedback)
        
        # Wait for result
        logger.info("Waiting for trajectory completion...")
        result: FollowJointTrajectoryResult = handle.get_result(timeout=10.0)
        
        logger.info(f"Trajectory completed! Final error: {result.final_error:.3f}, Time: {result.execution_time:.1f}s")
        
    except Exception as e:
        logger.error(f"Action failed: {e}")
    finally:
        client.stop()


def run_client_with_cancel():
    """Run client that cancels the action partway through"""
    # Create client for specific action channel
    client = ActionClient(
        "/demo_robot/follow_trajectory",
        FollowJointTrajectoryGoal,
        FollowJointTrajectoryFeedback,
        FollowJointTrajectoryResult,
        "cancel_client_16"
    )
    
    logger.info("Sending trajectory goal that will be cancelled...")
    
    try:
        # Create a longer trajectory
        points = []
        for i in range(10):  # More points for longer execution
            point = JointTrajectoryPoint()
            point.num_positions = 6
            point.positions = [float(i) * 0.1] * 6
            point.velocities = [0.0] * 6
            point.accelerations = [0.0] * 6
            point.time_from_start = float(i + 1)
            points.append(point)
        
        # Create goal object
        goal = FollowJointTrajectoryGoal()
        goal.num_joints = 6
        goal.joint_names = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
        goal.num_points = len(points)
        goal.points = points
        
        # Send goal with typed object
        handle = client.send_goal(goal)
        
        # Add feedback callback
        def on_feedback(feedback: FollowJointTrajectoryFeedback):
            logger.info(f"Progress: {feedback.progress:.1%}, Point: {feedback.current_point}")
            # Cancel after 50% progress
            if feedback.progress > 0.5:
                logger.info("Cancelling action...")
                handle.cancel()
        
        handle.add_feedback_callback(on_feedback)
        
        # Wait for result (should be cancelled)
        try:
            result: FollowJointTrajectoryResult = handle.get_result(timeout=10.0)
            logger.info("Action completed unexpectedly")
        except Exception as e:
            logger.info(f"Action cancelled as expected: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        client.stop()


def main():
    """Main entry point"""
    if len(sys.argv) != 2 or sys.argv[1] not in ["server", "client", "cancel"]:
        print(f"Usage: {sys.argv[0]} [server|client|cancel]")
        print("")
        print("This example demonstrates the new type-safe LCMware action API:")
        print("- ActionClient and ActionServer are bound to specific channels and types")
        print("- No more generic calls with dictionaries - use typed LCM objects")
        print("- Feedback and results are fully type-safe")
        print("- Single shared LCM instance managed automatically")
        sys.exit(1)
    
    if sys.argv[1] == "server":
        run_server()
    elif sys.argv[1] == "client":
        run_client()
    else:  # cancel
        run_client_with_cancel()


if __name__ == "__main__":
    main()