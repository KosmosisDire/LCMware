# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LCMware is a lightweight RPC framework built on top of LCM (Lightweight Communications and Marshaling) that provides services and actions while leveraging LCM's native pub/sub and type marshaling. It uses strongly-typed LCM messages instead of generic byte arrays.

## Architecture

The framework supports three communication patterns:

1. **Topics**: Direct LCM pub/sub with channels like `/{namespace}/{topic_name}`
2. **Services**: Request/Response pattern with typed requests and responses
   - Request: `/{namespace}/svc/{service_name}/req`
   - Response: `/{namespace}/svc/{service_name}/rsp/{client_id}`
3. **Actions**: Long-running operations with feedback and cancellation
   - Goal: `/{namespace}/act/{action_name}/goal`
   - Cancel: `/{namespace}/act/{action_name}/cancel`
   - Feedback: `/{namespace}/act/{action_name}/fb/{goal_id}`
   - Result: `/{namespace}/act/{action_name}/res/{goal_id}`

## Code Structure

- `python/lcmrpc/`: Main Python package
  - `service.py`: ServiceClient and ServiceServer classes
  - `action.py`: ActionClient, ActionServer, and ActionHandle classes
  - `constants.py`: Framework constants (action statuses, limits)
- `lcm_types/`: LCM type definitions
  - `rpc_types.lcm`: Core framework types (Header, ServiceResponseHeader, ActionCancel, ActionStatus)
- `python/examples/`: Demo applications showing usage patterns

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
python service_demo.py server    # Run service server
python service_demo.py client    # Run service client (in separate terminal)
```

## Key Design Principles

- **Type Safety**: All messages use strongly-typed LCM structures
- **Channel Naming**: Consistent naming convention for different message types
- **Client Identification**: Client names limited to 16 characters for reliable channel naming
- **Thread Safety**: Services and actions handle concurrent requests safely
- **Resource Management**: Proper subscription cleanup and thread management

## Important Constants

- `MAX_CLIENT_NAME_LENGTH = 16`: Maximum length for client names
- Action statuses: ACCEPTED(1), EXECUTING(2), SUCCEEDED(3), ABORTED(4), CANCELED(5)

## Dependencies

- `lcm`: Core LCM library for pub/sub and type marshaling
- Python 3.6+ required