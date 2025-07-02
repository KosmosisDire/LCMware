import argparse
from lcmware import ActionClient
from lcmware.types.grip import GripCommand, GripFeedback, GripResult

def state_str(state):
    if state == GripFeedback.MOVING:
        return "MOVING"
    elif state == GripFeedback.FINISHED:
        return "FINISHED"
    elif state == GripFeedback.OBJECT_FOUND:
        return "OBJECT_FOUND"
    else:
        return "UNKNOWN"

def main():
    parser = argparse.ArgumentParser(description="Control gripper via CLI")
    parser.add_argument("--state", choices=["open", "close"], default="open", 
                       help="Gripper state (open/close)")
    parser.add_argument("--speed", type=float, default=0.5, 
                       help="Speed (0-255)")
    parser.add_argument("--force", type=float, default=0.1, 
                       help="Force (0-255)")
    
    args = parser.parse_args()
    
    client = ActionClient("gipper_command", GripCommand, GripFeedback, GripResult, "grip_test")
    
    gripCmd = GripCommand()
    gripCmd.position = 0.0 if args.state == "open" else 1.0
    gripCmd.speed = args.speed
    gripCmd.force = args.force
    
    print(f"Sending command: state={args.state}, speed={args.speed}, force={args.force}")
    
    handle = client.send_goal(gripCmd)
    handle.add_feedback_callback(lambda feedback: print(f"Feedback: position={feedback.position}, state={state_str(feedback.state)}"))
    
    result = handle.get_result()
    print(f"Result: {result.status.message}, state: {state_str(result.state)}")

if __name__ == "__main__":
    main()