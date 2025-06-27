#pragma once

namespace lcmware {

// Client name constraints
constexpr int MAX_CLIENT_NAME_LENGTH = 16;

// Action status constants
enum class ActionStatus : int {
    ACCEPTED = 1,
    EXECUTING = 2,
    SUCCEEDED = 3,
    ABORTED = 4,
    CANCELED = 5
};

}