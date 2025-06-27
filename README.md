# LCMware

A lightweight RPC framework built on top of [LCM (Lightweight Communications and Marshaling)](https://lcm-proj.github.io/) that provides services and actions using strongly-typed LCM messages.

## Features

- **Services**: Synchronous request/response pattern
- **Actions**: Long-running operations with feedback and cancellation
- **Type Safety**: All messages use strongly-typed LCM structures
- **Multi-Language**: Python and C++ implementations
- **Thread Safe**: Concurrent request handling

## Prerequisites

- LCM (>= 1.3.0)
- Python 3.6+ (for Python library)
- C++17 compiler (for C++ library)
- CMake 3.10+ (for C++ library)

## Installation

### Python

```bash
cd python
pip install -e .
```

### C++

```bash
cd cpp
mkdir build && cd build
cmake ..
make
sudo make install  # Optional: install system-wide
```

## Usage

### Python Services

**Server:**
```python
from lcmware import ServiceServer
from lcmware.types.examples import AddNumbersRequest, AddNumbersResponse

server = ServiceServer("my_robot")

def add_numbers_handler(request: AddNumbersRequest) -> dict:
    return {"sum": request.a + request.b}

server.register_service("add_numbers", AddNumbersRequest, AddNumbersResponse, 
                       add_numbers_handler)
server.spin()
```

**Client:**
```python
from lcmware import ServiceClient
from lcmware.types.examples import AddNumbersRequest, AddNumbersResponse

client = ServiceClient("my_robot", "math_client")
response = client.call("add_numbers", AddNumbersRequest, AddNumbersResponse, {
    "a": 5.0,
    "b": 3.0
})
print(f"Result: {response.sum}")
```

### Python Actions

**Server:**
```python
from lcmware import ActionServer
from lcmware.types.examples import (
    FollowJointTrajectoryGoal, 
    FollowJointTrajectoryFeedback,
    FollowJointTrajectoryResult
)

server = ActionServer("my_robot")

def trajectory_handler(goal, send_feedback):
    for i in range(goal.num_points):
        send_feedback({"current_point": i}, progress=(i+1)/goal.num_points)
        # Process point...
    return {"final_error": 0.001}

server.register_action("follow_trajectory", 
                      FollowJointTrajectoryGoal,
                      FollowJointTrajectoryFeedback, 
                      FollowJointTrajectoryResult,
                      trajectory_handler)
server.spin()
```

**Client:**
```python
from lcmware import ActionClient
from lcmware.types.examples import (
    FollowJointTrajectoryGoal,
    FollowJointTrajectoryFeedback,
    FollowJointTrajectoryResult
)

client = ActionClient("my_robot", "traj_client")
handle = client.send_goal("follow_trajectory", 
                         FollowJointTrajectoryGoal,
                         FollowJointTrajectoryFeedback,
                         FollowJointTrajectoryResult,
                         {"num_points": 10})

handle.add_feedback_callback(lambda fb: print(f"Progress: {fb.progress}"))
result = handle.get_result(timeout=10.0)
```

### C++ Services

**Server:**
```cpp
#include <lcmware/service.hpp>
#include <lcmware/types/examples/AddNumbersRequest.hpp>
#include <lcmware/types/examples/AddNumbersResponse.hpp>

using namespace lcmware;

ServiceServer<examples::AddNumbersRequest, 
              examples::AddNumbersResponse> server("my_robot");

auto handler = [](const examples::AddNumbersRequest& req) -> examples::AddNumbersResponse {
    examples::AddNumbersResponse resp;
    resp.sum = req.a + req.b;
    return resp;
};

server.register_service("add_numbers", handler);
server.spin();
```

**Client:**
```cpp
#include <lcmware/service.hpp>
#include <lcmware/types/examples/AddNumbersRequest.hpp>
#include <lcmware/types/examples/AddNumbersResponse.hpp>

using namespace lcmware;

ServiceClient<examples::AddNumbersRequest, 
              examples::AddNumbersResponse> client("my_robot", "cpp_client");

examples::AddNumbersRequest request;
request.a = 5.0;
request.b = 3.0;

auto response = client.call("add_numbers", request);
std::cout << "Result: " << response.sum << std::endl;
```

### C++ Actions

**Server:**
```cpp
#include <lcmware/action.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryGoal.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryFeedback.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryResult.hpp>

using namespace lcmware;

ActionServer<examples::FollowJointTrajectoryGoal,
             examples::FollowJointTrajectoryFeedback,
             examples::FollowJointTrajectoryResult> server("my_robot");

auto handler = [](const auto& goal, auto send_feedback) -> auto {
    for (int i = 0; i < goal.num_points; ++i) {
        examples::FollowJointTrajectoryFeedback feedback;
        feedback.current_point = i;
        feedback.progress = (i + 1.0) / goal.num_points;
        send_feedback(feedback);
        // Process point...
    }
    examples::FollowJointTrajectoryResult result;
    result.final_error = 0.001;
    return result;
};

server.register_action("follow_trajectory", handler);
server.spin();
```

**Client:**
```cpp
#include <lcmware/action.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryGoal.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryFeedback.hpp>
#include <lcmware/types/examples/FollowJointTrajectoryResult.hpp>

using namespace lcmware;

ActionClient<examples::FollowJointTrajectoryGoal,
             examples::FollowJointTrajectoryFeedback,
             examples::FollowJointTrajectoryResult> client("my_robot", "cpp_client");

examples::FollowJointTrajectoryGoal goal;
goal.num_points = 10;
// ... set other goal fields ...

auto handle = client.send_goal("follow_trajectory", goal);
handle->add_feedback_callback([](const auto& fb) {
    std::cout << "Progress: " << (fb.progress * 100) << "%" << std::endl;
});

auto result = handle->get_result(10.0);
std::cout << "Final error: " << result.final_error << std::endl;
```

## Examples

Run the example programs to see the framework in action:

### Python
```bash
# Terminal 1 - Service Server
python python/examples/service_demo.py server

# Terminal 2 - Service Client
python python/examples/service_demo.py client

# Terminal 1 - Action Server
python python/examples/action_demo.py server

# Terminal 2 - Action Client
python python/examples/action_demo.py client
```

### C++
```bash
# Build examples with -DBUILD_EXAMPLES=ON
cd cpp/build
cmake .. -DBUILD_EXAMPLES=ON
make

# Terminal 1 - Service Server
./examples/service_demo server

# Terminal 2 - Service Client
./examples/service_demo client

# Terminal 1 - Action Server
./examples/action_demo server

# Terminal 2 - Action Client
./examples/action_demo client
```

## Creating Custom Types

Define your own LCM types in `.lcm` files:

```
package myproject;

struct MyRequest {
    core.Header header;  // Required for requests
    double value;
}

struct MyResponse {
    core.ServiceResponseHeader response_header;  // Required for responses
    double result;
}

struct MyGoal {
    core.Header header;  // Required for goals
    int32_t count;
}

struct MyFeedback {
    core.Header header;  // Required for feedback
    double progress;
    int32_t current;
}

struct MyResult {
    core.ActionStatus status;  // Required for results
    double final_value;
}
```

Generate bindings:
```bash
cd lcm_types
./generate_types.sh  # Generates Python and C++ bindings
```

## Channel Naming Convention

- **Services**: 
  - Request: `/{namespace}/svc/{service_name}/req`
  - Response: `/{namespace}/svc/{service_name}/rsp/{client_id}`
- **Actions**:
  - Goal: `/{namespace}/act/{action_name}/goal`
  - Cancel: `/{namespace}/act/{action_name}/cancel`
  - Feedback: `/{namespace}/act/{action_name}/fb/{goal_id}`
  - Result: `/{namespace}/act/{action_name}/res/{goal_id}`

## Important Notes

- Client names are limited to 16 characters (MAX_CLIENT_NAME_LENGTH)
- All request types must have a `core.Header header` field
- All response types must have a `core.ServiceResponseHeader response_header` field
- All action types must have appropriate header fields as shown above

## License

MIT License - see LICENSE file for details.