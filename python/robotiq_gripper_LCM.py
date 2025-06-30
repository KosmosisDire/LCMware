import serial
import time, struct
import binascii

import sys, logging
from lcmware.types.grip import (
    GripCommand, 
    GripFeedback,
    GripResult
)
from lcmware import ActionClient, ActionServer

### CONFIGURE YOUR PORT HERE ###
PORT     = '/dev/ttyUSB0'
BAUDRATE = 115200
TIMEOUT  = 1

SPEED = 255  # set default speed for the gripper ; (0-255)
FORCE = 255  # set default force for the gripper ; (0-255)

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

def openGripper(speed: int, force: int):
    """Open the gripper by sending the appropriate command."""
    ser.write(getMoveHex(0, speed, force))
    resp = ser.read(ser.in_waiting or 8)
    logger.info(f'OPEN → {binascii.hexlify(resp)}')


def closeGripper(speed: int, force: int):
    """Close the gripper by sending the appropriate command."""
    ser.write(getMoveHex(255, speed, force))
    move_resp = ser.read(ser.in_waiting or 8)
    logger.info(f'CLOSE → {binascii.hexlify(move_resp)}')

    ser.write(bytes.fromhex(f'09 04 07 D0 00 03 B1 CE'))
    grip_resp = binascii.hexlify(ser.read(ser.in_waiting or 8))
    while grip_resp[3] != 0xf9:
        time.sleep(0.1)
        ser.write(bytes.fromhex(f'09 04 07 D0 00 03 B1 CE'))
        grip_resp = binascii.hexlify(ser.read(ser.in_waiting or 8))
    logger.info(f'GRIP RESPONSE → {binascii.hexlify(grip_resp)}')

    return grip_resp


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
    
    server = ActionServer("gipper")

    ### Start Main Loop ###
    try:
        while True:

            def handler(cmd):
                logger.info(f"Executing Command; Gripper {cmd.state}")
                if cmd.state == 0:      # Open
                    openGripper(cmd.speed, cmd.force)
                elif cmd.state == 1:    # Close
                    resp = closeGripper(cmd.speed, cmd.force)

                else:
                    logger.error("Unknown command state")
                    return 0

            server.register_action(
                "gripper_command",
                GripCommand,
                GripFeedback,
                GripResult,
                handler
            )
            
            logger.info("Starting action server...")
            server.spin()
    finally:
        ser.close()

if __name__ == "__main__":
    main()