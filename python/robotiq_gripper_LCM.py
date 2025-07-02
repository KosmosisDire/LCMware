from typing import Callable
import serial
import time, struct
import binascii

import sys, logging
from lcmware.types.grip import (
    GripCommand, 
    GripFeedback,
    GripResult
)
from lcmware.types.core import ActionStatus
from lcmware import ActionClient, ActionServer
import lcmware

### CONFIGURE YOUR PORT HERE ###
PORT     = '/dev/ttyUSB0'
BAUDRATE = 115200
TIMEOUT  = 1

def getHex(toHexInt: int) -> bytes:
    return hex(toHexInt)[2:].zfill(2).upper()

### Startup Commands ###
CLEAR_F    = bytes.fromhex(f'09 10 03 E8 00 03 06 00 00 00 00 00 00 73 30')
ACTIVATE_F = bytes.fromhex(f'09 10 03 E8 00 03 06 01 00 00 00 00 00 72 E1')

### OPEN SERIAL PORT ###
ser = serial.Serial(
    port=PORT,
    baudrate=BAUDRATE,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=TIMEOUT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def getMoveHex(position: int,  speed: int, force: int) -> bytes:
    position_hex = hex(position)[2:].zfill(2).upper()
    speed_hex = hex(speed)[2:].zfill(2).upper()
    force_hex = hex(force)[2:].zfill(2).upper()
    """Calculates the Modbus RTU CRC16."""
    grip_pos = bytes.fromhex(f'09 10 03 E8 00 03 06 09 00 00 {position_hex} {speed_hex} {force_hex}')

    crc = 0xFFFF
    polynomial = 0xA001  # Standard Modbus CRC polynomial
    for byte_val in grip_pos: 
        crc ^= byte_val
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= polynomial
            else:
                crc >>= 1
    crc = struct.pack('<H', crc)
    # print(grip_pos)
    return grip_pos + crc

def moveGripper(position: float, speed: int, force: int, feedback: Callable[[GripFeedback], None]) -> GripResult:
    """Move the gripper to specified position (0=fully open, 1=fully closed)."""
    # Validate position range
    if not 0 <= position <= 1:
        result = GripResult()
        result.status = ActionStatus()
        result.status.status = lcmware.ActionStatus.ABORTED
        result.status.message = f"Invalid position {position}. Must be between 0-1."
        return result
    
    # Send move command
    ser.write(getMoveHex(int(position * 255), int(speed * 255), int(force * 255)))
    move_resp = ser.read(ser.in_waiting or 8)
    action = "OPEN" if position <= 0.01 else "CLOSE" if position >= 0.99 else f"MOVE_TO_{position}"
    logger.info(f'{action} → {binascii.hexlify(move_resp)}')

    # Poll for status updates
    ser.write(bytes.fromhex(f'09 04 07 D0 00 03 B1 CE'))
    grip_resp = ser.read(ser.in_waiting or 8)

    state_byte = 0
    state = GripFeedback.MOVING
    position = 0

    while len(grip_resp) != 11 or state is GripFeedback.MOVING:
        time.sleep(0.1)
        ser.write(bytes.fromhex(f'09 04 07 D0 00 03 B1 CE'))
        grip_resp = ser.read(ser.in_waiting or 8)
        if len(grip_resp) == 11:
            state_byte = grip_resp[3]
            position = grip_resp[7] / float(255)
            print(f"State: {state}, Position: {position}")
            match state_byte:
                case 0xF9:
                    state = GripFeedback.FINISHED
                case 0xB9 | 0x79:
                    state = GripFeedback.OBJECT_FOUND
                case _:
                    state = GripFeedback.MOVING

            feed = GripFeedback()
            feed.state = state
            feed.position = position

            feedback(feed)

    # Generate appropriate result message
    if state == GripFeedback.FINISHED:
        if position <= 0.01:
            message = "Gripper opened fully"
        elif position >= 0.99:
            message = "Gripper closed fully"
        else:
            message = f"Gripper moved to position {position}"
    else:  # OBJECT_FOUND
        message = f"Gripper found an object and stopped at position {position:.2f}"

    result = GripResult()
    result.status = ActionStatus()
    result.status.status = lcmware.ActionStatus.SUCCEEDED
    result.status.message = message
    result.state = state
    result.position = position

    return result

def handler(cmd: GripCommand, feedback: Callable[[GripFeedback], None]) -> GripResult:
    logger.info(f"Executing Command; Gripper pos: {cmd.position}")
    
    result = GripResult()
    result.status = ActionStatus()
    result.status.status = lcmware.ActionStatus.ABORTED

    if (cmd.position < 0 or cmd.position > 1):
        result.status.message = f"Invalid position {cmd.position}. Must be between 0 and 1."
        return result
    if (cmd.speed < 0 or cmd.speed > 1):
        result.status.message = f"Invalid speed {cmd.speed}. Must be between 0 and 1."
        return result
    if (cmd.force < 0 or cmd.force > 1):
        result.status.message = f"Invalid force {cmd.force}. Must be between 0 and 1."
        return result

    result = moveGripper(cmd.position, cmd.speed, cmd.force, feedback)
    return result

    

def main():
    ### initialization ###
    ser.write(CLEAR_F)
    resp = ser.read(ser.in_waiting or 8)
    logger.info(f'CLEAR → {binascii.hexlify(resp)}')
    time.sleep(0.1)

    ser.write(ACTIVATE_F)
    resp = ser.read(ser.in_waiting or 8)
    logger.info(f'ACTIVATE → {binascii.hexlify(resp)}')
    time.sleep(0.5)
    
    server = ActionServer("gipper_command", GripCommand, GripFeedback, GripResult, handler)

    logger.info("Starting action server...")
    server.spin()

    ser.close()

if __name__ == "__main__":
    main()