# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LCMware is a lightweight RPC framework built on top of LCM (Lightweight Communications and Marshaling) that provides type-safe topics, services, and actions while leveraging LCM's native pub/sub and type marshaling. It uses strongly-typed LCM messages with a single managed LCM instance.

## Architecture

The framework supports three communication patterns:

1. **Topics**: Direct LCM pub/sub with full channel paths like `/robot/sensors/camera`
   - TopicPublisher and TopicSubscriber bound to specific channels and message types
2. **Services**: Request/Response pattern with typed requests and responses
   - Request: `{service_channel}/req`
   - Response: `{service_channel}/rsp/{client_id}`
   - ServiceClient and ServiceServer bound to specific service channels
3. **Actions**: Long-running operations with feedback and cancellation
   - Goal: `{action_channel}/goal`
   - Cancel: `{action_channel}/cancel`
   - Feedback: `{action_channel}/fb/{goal_id}`
   - Result: `{action_channel}/res/{goal_id}`
   - ActionClient and ActionServer bound to specific action channels

## Code Structure

- `python/lcmware/`: Main Python package
  - `manager.py`: LCMManager singleton for shared LCM instance
  - `topic.py`: TopicPublisher and TopicSubscriber classes
  - `service.py`: Type-safe ServiceClient and ServiceServer classes
  - `action.py`: Type-safe ActionClient, ActionServer, and ActionHandle classes
  - `constants.py`: Framework constants (action statuses, limits)
- `cpp/lcmware/`: Main C++ package
  - `manager.hpp`: LCMManager singleton for shared LCM instance
  - `topic.hpp`: TopicPublisher and TopicSubscriber templates
  - `service.hpp`: Type-safe ServiceClient and ServiceServer templates
  - `action.hpp`: Type-safe ActionClient, ActionServer, and ActionHandle templates
- `lcm_types/`: LCM type definitions
  - `core.lcm`: Core framework types (Header, ServiceResponseHeader, ActionCancel, ActionStatus)
  - `examples.lcm`: Example message types for demos
- `python/examples/`: Demo applications showing new type-safe usage patterns
- `cpp/examples/`: C++ demo applications showing new type-safe usage patterns

## Development Commands

### Generate LCM Types
```bash
cd lcm_types
./generate_types.sh        # Generate both Python and C++ types
```

### Python Development
```bash
cd python
pip install -e .           # Install in development mode
```

### Run Examples
```bash
cd python/examples
python topic_demo.py publisher   # Run topic publisher
python topic_demo.py subscriber  # Run topic subscriber (in separate terminal)
python topic_demo.py multi       # Run multi-topic demo
python service_demo.py server    # Run service server
python service_demo.py client    # Run service client (in separate terminal)
python action_demo.py server     # Run action server
python action_demo.py client     # Run action client (in separate terminal)
```

### C++ Development
```bash
cd cpp
mkdir build && cd build
cmake ..
make
```

### Run C++ Examples
```bash
cd cpp/build
./topic_demo publisher       # Run C++ topic publisher
./topic_demo subscriber      # Run C++ topic subscriber (in separate terminal)
./topic_demo multi           # Run C++ multi-topic demo
./service_demo server        # Run C++ service server
./service_demo client        # Run C++ service client (in separate terminal)
./action_demo server         # Run C++ action server
./action_demo client         # Run C++ action client (in separate terminal)
```

## Key Design Principles

- **Type Safety**: All messages use strongly-typed LCM structures with compile-time/runtime validation
- **Single-Purpose Classes**: Each client/server bound to specific channel and message types
- **Managed LCM Instance**: Single shared LCM instance managed by singleton pattern
- **Channel-Centric Design**: Full channel paths specified at construction time
- **Thread Safety**: Services and actions handle concurrent requests safely
- **Resource Management**: Automatic subscription cleanup and thread management

## Important Constants

- `MAX_CLIENT_NAME_LENGTH = 16`: Maximum length for client names
- Action statuses: ACCEPTED(1), EXECUTING(2), SUCCEEDED(3), ABORTED(4), CANCELED(5)

## New API Usage Examples

### Topics (Python)
```python
from lcmware import TopicPublisher, TopicSubscriber
from lcmware.types.examples import ImageMessage

# Publisher bound to specific channel and type
pub = TopicPublisher("/robot/sensors/camera", ImageMessage)
image = ImageMessage()
image.width = 640
image.height = 480
pub.publish(image)

# Subscriber bound to specific channel and type
def callback(msg: ImageMessage):
    print(f"Received image: {msg.width}x{msg.height}")

sub = TopicSubscriber("/robot/sensors/camera", ImageMessage, callback)
```

### Services (Python)
```python
from lcmware import ServiceClient, ServiceServer
from lcmware.types.examples import AddNumbersRequest, AddNumbersResponse

# Client bound to specific service channel and types
client = ServiceClient("/robot/add_numbers", AddNumbersRequest, AddNumbersResponse)
request = AddNumbersRequest()
request.a = 5.0
request.b = 3.0
response = client.call(request)

# Server bound to specific service channel and types
def handler(req: AddNumbersRequest) -> AddNumbersResponse:
    resp = AddNumbersResponse()
    resp.sum = req.a + req.b
    return resp

server = ServiceServer("/robot/add_numbers", AddNumbersRequest, AddNumbersResponse, handler)
```

### Actions (Python)
```python
from lcmware import ActionClient, ActionServer
from lcmware.types.examples import MoveGoal, MoveFeedback, MoveResult

# Client bound to specific action channel and types
client = ActionClient("/robot/move", MoveGoal, MoveFeedback, MoveResult)
goal = MoveGoal()
goal.target_x = 1.0
goal.target_y = 2.0
handle = client.send_goal(goal)
result = handle.get_result()

# Server bound to specific action channel and types
def handler(goal: MoveGoal, send_feedback) -> MoveResult:
    feedback = MoveFeedback()
    feedback.progress = 0.5
    send_feedback(feedback)
    
    result = MoveResult()
    result.success = True
    return result

server = ActionServer("/robot/move", MoveGoal, MoveFeedback, MoveResult, handler)
```

### Topics (C++)
```cpp
#include <lcmware/topic.hpp>
#include <lcmware/types/examples/ImageMessage.hpp>

using namespace lcmware;

// Publisher bound to specific channel and type
TopicPublisher<examples::ImageMessage> pub("/robot/sensors/camera");
examples::ImageMessage image;
image.width = 640;
image.height = 480;
pub.publish(image);

// Subscriber bound to specific channel and type
auto callback = [](const examples::ImageMessage& msg) {
    std::cout << "Received image: " << msg.width << "x" << msg.height << std::endl;
};
TopicSubscriber<examples::ImageMessage> sub("/robot/sensors/camera", callback);
```

### Services (C++)
```cpp
#include <lcmware/service.hpp>
#include <lcmware/types/examples/AddNumbersRequest.hpp>
#include <lcmware/types/examples/AddNumbersResponse.hpp>

using namespace lcmware;

// Client bound to specific service channel and types
ServiceClient<examples::AddNumbersRequest, examples::AddNumbersResponse> client("/robot/add_numbers");
examples::AddNumbersRequest request;
request.a = 5.0;
request.b = 3.0;
auto response = client.call(request);

// Server bound to specific service channel and types
auto handler = [](const examples::AddNumbersRequest& req) -> examples::AddNumbersResponse {
    examples::AddNumbersResponse resp;
    resp.sum = req.a + req.b;
    return resp;
};
ServiceServer<examples::AddNumbersRequest, examples::AddNumbersResponse> server("/robot/add_numbers", handler);
```

### Actions (C++)
```cpp
#include <lcmware/action.hpp>
#include <lcmware/types/examples/MoveGoal.hpp>
#include <lcmware/types/examples/MoveFeedback.hpp>
#include <lcmware/types/examples/MoveResult.hpp>

using namespace lcmware;

// Client bound to specific action channel and types
ActionClient<examples::MoveGoal, examples::MoveFeedback, examples::MoveResult> client("/robot/move");
examples::MoveGoal goal;
goal.target_x = 1.0;
goal.target_y = 2.0;
auto handle = client.send_goal(goal);
auto result = handle->get_result();

// Server bound to specific action channel and types
auto handler = [](const examples::MoveGoal& goal, auto send_feedback) -> examples::MoveResult {
    examples::MoveFeedback feedback;
    feedback.progress = 0.5;
    send_feedback(feedback);
    
    examples::MoveResult result;
    result.success = true;
    return result;
};
ActionServer<examples::MoveGoal, examples::MoveFeedback, examples::MoveResult> server("/robot/move", handler);
```

## Dependencies

- `lcm`: Core LCM library for pub/sub and type marshaling
- Python 3.6+ required