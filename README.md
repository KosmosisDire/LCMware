# LCMware

A lightweight RPC framework built on top of [LCM (Lightweight Communications and Marshaling)](https://lcm-proj.github.io/) that provides type-safe topics, services, and actions with strongly-typed LCM messages and a single managed LCM instance.

## Features

- **Topics**: Direct LCM pub/sub with full channel paths like `/robot/sensors/camera`
- **Services**: Synchronous request/response pattern
- **Actions**: Long-running operations with feedback and cancellation
- **Type Safety**: All publishers/subscribers/clients/servers bound to specific channels and message types
- **Single-Purpose Classes**: Each client/server represents one channel with one message type set
- **Managed LCM Instance**: Single shared LCM instance managed automatically
- **Multi-Language**: Python and C++ implementations with identical APIs
- **Thread Safe**: Concurrent request handling with automatic thread management

## Prerequisites

- **LCM** (>= 1.3.0) - `sudo apt install liblcm-dev lcm-python3` (Ubuntu/Debian)
- **Python 3.6+** (for Python library)
- **C++17 compiler** (for C++ library) - g++, clang++
- **CMake 3.10+** (for C++ library)

## Installation

### Generate LCM Types (Required First)
```bash
cd lcm_types
./generate_types.sh        # Generates both Python and C++ types
```

### Python Installation
```bash
cd python
pip install -e .           # Install in development mode
```

### C++ Installation
```bash
cd cpp
mkdir build && cd build
cmake .. -DBUILD_EXAMPLES=ON
make
sudo make install          # Optional: install system-wide
```

## Quick Start Examples

### Topics (Pub/Sub)

**Python Publisher:**
```python
from lcmware import TopicPublisher
from lcmware.types.examples import ImageMessage

# Publisher bound to specific channel and type
pub = TopicPublisher("/robot/sensors/camera", ImageMessage)

image = ImageMessage()
image.width = 640
image.height = 480
image.channels = 3
image.encoding = "rgb8"
image.data_size = 100
image.data = [255] * 100

pub.publish(image)
```

**Python Subscriber:**
```python
from lcmware import TopicSubscriber
from lcmware.types.examples import ImageMessage

def image_callback(msg: ImageMessage):
    print(f"Received image: {msg.width}x{msg.height}")

# Subscriber bound to specific channel and type
sub = TopicSubscriber("/robot/sensors/camera", ImageMessage, image_callback)

# Keep alive
try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    sub.unsubscribe()
```

**C++ Publisher:**
```cpp
#include <lcmware/topic.hpp>
#include <lcmware/types/examples/ImageMessage.hpp>

using namespace lcmware;

// Publisher bound to specific channel and type
TopicPublisher<examples::ImageMessage> pub("/robot/sensors/camera");

examples::ImageMessage image;
image.width = 640;
image.height = 480;
image.channels = 3;
image.encoding = "rgb8";
image.data_size = 100;
image.data.resize(100, 255);

pub.publish(image);
```

**C++ Subscriber:**
```cpp
#include <lcmware/topic.hpp>
#include <lcmware/types/examples/ImageMessage.hpp>

using namespace lcmware;

auto callback = [](const examples::ImageMessage& msg) {
    std::cout << "Received image: " << msg.width << "x" << msg.height << std::endl;
};

// Subscriber bound to specific channel and type
TopicSubscriber<examples::ImageMessage> sub("/robot/sensors/camera", callback);

// Keep alive
while (true) {
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}
```

### Services (Request/Response)

**Python Service Server:**
```python
from lcmware import ServiceServer
from lcmware.types.examples import AddNumbersRequest, AddNumbersResponse

def add_numbers_handler(request: AddNumbersRequest) -> AddNumbersResponse:
    response = AddNumbersResponse()
    response.sum = request.a + request.b
    return response

# Server bound to specific service channel and types
server = ServiceServer("/demo_robot/add_numbers", 
                      AddNumbersRequest, AddNumbersResponse, 
                      add_numbers_handler)
server.spin()
```

**Python Service Client:**
```python
from lcmware import ServiceClient
from lcmware.types.examples import AddNumbersRequest, AddNumbersResponse

# Client bound to specific service channel and types
client = ServiceClient("/demo_robot/add_numbers", 
                      AddNumbersRequest, AddNumbersResponse, 
                      "math_client")

request = AddNumbersRequest()
request.a = 5.0
request.b = 3.0

response = client.call(request)
print(f"Result: {response.sum}")
```

**C++ Service Server:**
```cpp
#include <lcmware/service.hpp>
#include <lcmware/types/examples/AddNumbersRequest.hpp>
#include <lcmware/types/examples/AddNumbersResponse.hpp>

using namespace lcmware;

auto handler = [](const examples::AddNumbersRequest& req) -> examples::AddNumbersResponse {
    examples::AddNumbersResponse resp;
    resp.sum = req.a + req.b;
    return resp;
};

// Server bound to specific service channel and types
ServiceServer<examples::AddNumbersRequest, examples::AddNumbersResponse> 
    server("/demo_robot/add_numbers", handler);
server.spin();
```

**C++ Service Client:**
```cpp
#include <lcmware/service.hpp>
#include <lcmware/types/examples/AddNumbersRequest.hpp>
#include <lcmware/types/examples/AddNumbersResponse.hpp>

using namespace lcmware;

// Client bound to specific service channel and types
ServiceClient<examples::AddNumbersRequest, examples::AddNumbersResponse> 
    client("/demo_robot/add_numbers", "cpp_client");

examples::AddNumbersRequest request;
request.a = 5.0;
request.b = 3.0;

auto response = client.call(request);
std::cout << "Result: " << response.sum << std::endl;
```

### Actions (Long-running Operations)

**Python Action Server:**
```python
from lcmware import ActionServer
from lcmware.types.examples import (
    FollowJointTrajectoryGoal, 
    FollowJointTrajectoryFeedback,
    FollowJointTrajectoryResult
)

def trajectory_handler(goal: FollowJointTrajectoryGoal, send_feedback) -> FollowJointTrajectoryResult:
    for i in range(goal.num_points):
        feedback = FollowJointTrajectoryFeedback()
        feedback.current_point = i
        feedback.progress = (i + 1) / goal.num_points
        send_feedback(feedback)
        
        time.sleep(0.1)  # Simulate work
    
    result = FollowJointTrajectoryResult()
    result.final_error = 0.001
    return result

# Server bound to specific action channel and types
server = ActionServer("/demo_robot/follow_trajectory",
                     FollowJointTrajectoryGoal,
                     FollowJointTrajectoryFeedback, 
                     FollowJointTrajectoryResult,
                     trajectory_handler)
server.spin()
```

**Python Action Client:**
```python
from lcmware import ActionClient
from lcmware.types.examples import (
    FollowJointTrajectoryGoal,
    FollowJointTrajectoryFeedback,
    FollowJointTrajectoryResult
)

# Client bound to specific action channel and types
client = ActionClient("/demo_robot/follow_trajectory",
                     FollowJointTrajectoryGoal,
                     FollowJointTrajectoryFeedback,
                     FollowJointTrajectoryResult,
                     "traj_client")

goal = FollowJointTrajectoryGoal()
goal.num_joints = 6
goal.joint_names = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
goal.num_points = 10
# ... set trajectory points ...

handle = client.send_goal(goal)
handle.add_feedback_callback(lambda fb: print(f"Progress: {fb.progress:.1%}"))

result = handle.get_result(timeout=10.0)
print(f"Final error: {result.final_error}")
```

## Running Examples

### Python Examples
```bash
cd python/examples

# Topic demo
python topic_demo.py publisher   # Terminal 1
python topic_demo.py subscriber  # Terminal 2

# Service demo  
python service_demo.py server    # Terminal 1
python service_demo.py client    # Terminal 2

# Action demo
python action_demo.py server     # Terminal 1
python action_demo.py client     # Terminal 2
```

### C++ Examples
```bash
cd cpp/build

# Topic demo
./examples/topic_demo publisher   # Terminal 1
./examples/topic_demo subscriber  # Terminal 2

# Service demo
./examples/service_demo server    # Terminal 1
./examples/service_demo client    # Terminal 2

# Action demo
./examples/action_demo server     # Terminal 1
./examples/action_demo client     # Terminal 2
```

## Development

### Using in Your C++ Project

**With CMake (Recommended):**
```cmake
find_package(PkgConfig REQUIRED)
pkg_check_modules(LCM REQUIRED lcm)

# If LCMware is installed system-wide
find_package(lcmware REQUIRED)
target_link_libraries(your_target lcmware ${LCM_LIBRARIES})

# Or if building from source
add_subdirectory(path/to/lcmware/cpp)
target_link_libraries(your_target lcmware)
```

**Manually:**
```bash
# Include directories
-I/path/to/lcmware/cpp -I/path/to/lcmware/cpp/lcmware/types

# Link libraries  
-llcm
```

### Creating Custom Message Types

1. **Define LCM types** in `lcm_types/your_package.lcm`:
```
package your_package;

struct ImageMessage {
    core.Header header;
    int32_t width;
    int32_t height;
    int32_t channels;
    string encoding;
    int32_t data_size;
    int8_t data[data_size];
}

struct ProcessImageRequest {
    core.Header header;
    string algorithm;
    ImageMessage image;
}

struct ProcessImageResponse {
    core.ServiceResponseHeader response_header;
    ImageMessage result;
    double processing_time;
}
```

2. **Generate bindings:**
```bash
cd lcm_types
./generate_types.sh
```

3. **Use in code:**
```python
from lcmware import TopicPublisher
from lcmware.types.your_package import ImageMessage

pub = TopicPublisher("/camera/raw", ImageMessage)
```

### Architecture

LCMware uses three communication patterns:

1. **Topics**: Direct LCM pub/sub with full channel paths
   - Publisher/Subscriber bound to specific channels and message types

2. **Services**: Request/Response pattern
   - Request: `{service_channel}/req`  
   - Response: `{service_channel}/rsp/{client_id}`

3. **Actions**: Long-running operations with feedback and cancellation
   - Goal: `{action_channel}/goal`
   - Cancel: `{action_channel}/cancel`
   - Feedback: `{action_channel}/fb/{goal_id}`
   - Result: `{action_channel}/res/{goal_id}`

### Key Design Principles

- **Type Safety**: All messages use strongly-typed LCM structures
- **Single-Purpose Classes**: Each client/server bound to specific channel and message types  
- **Managed LCM Instance**: Single shared LCM instance managed by singleton pattern
- **Channel-Centric Design**: Full channel paths specified at construction time
- **Thread Safety**: Services and actions handle concurrent requests safely
- **Resource Management**: Automatic subscription cleanup and thread management

### Important Notes

- **Client names**: Limited to 16 characters (`MAX_CLIENT_NAME_LENGTH`)
- **Action statuses**: `ACCEPTED(1)`, `EXECUTING(2)`, `SUCCEEDED(3)`, `ABORTED(4)`, `CANCELED(5)`
- **Headers required**: 
  - Service requests: `core.Header header`
  - Service responses: `core.ServiceResponseHeader response_header`  
  - Action goals/feedback: `core.Header header`
  - Action results: `core.ActionStatus status`

## Troubleshooting

### UDP Buffer Size Warning
If you see LCM warnings about large packets and UDP buffer size:

```bash
# Increase UDP buffer size (Linux)
sudo sysctl -w net.core.rmem_max=8388608
sudo sysctl -w net.core.rmem_default=8388608
```

Or reduce your message sizes for testing.

### Build Issues
- **Missing LCM**: Install with `sudo apt install liblcm-dev` (Ubuntu/Debian)
- **C++17 errors**: Ensure your compiler supports C++17 (`-std=c++17`)
- **Missing types**: Run `./lcm_types/generate_types.sh` first

## License

MIT License - see LICENSE file for details.