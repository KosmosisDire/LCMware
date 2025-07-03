"""Constants for lcmware framework"""

from enum import IntEnum

# Client name constraints
MAX_CLIENT_NAME_LENGTH = 16

# Action status constants
class ActionStatus(IntEnum):
    ACCEPTED = 1
    EXECUTING = 2
    SUCCEEDED = 3
    ABORTED = 4
    CANCELED = 5