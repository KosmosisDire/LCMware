"""LCM type definitions
This file automatically generated by lcm.
DO NOT MODIFY BY HAND!!!!
"""


from io import BytesIO
import struct

import core

class FollowJointTrajectoryResult(object):

    __slots__ = ["status", "final_error", "execution_time"]

    __typenames__ = ["core.ActionStatus", "double", "double"]

    __dimensions__ = [None, None, None]

    def __init__(self):
        self.status = core.ActionStatus()
        """ LCM Type: core.ActionStatus """
        self.final_error = 0.0
        """ LCM Type: double """
        self.execution_time = 0.0
        """ LCM Type: double """

    def encode(self):
        buf = BytesIO()
        buf.write(FollowJointTrajectoryResult._get_packed_fingerprint())
        self._encode_one(buf)
        return buf.getvalue()

    def _encode_one(self, buf):
        assert self.status._get_packed_fingerprint() == core.ActionStatus._get_packed_fingerprint()
        self.status._encode_one(buf)
        buf.write(struct.pack(">dd", self.final_error, self.execution_time))

    @staticmethod
    def decode(data: bytes):
        if hasattr(data, 'read'):
            buf = data
        else:
            buf = BytesIO(data)
        if buf.read(8) != FollowJointTrajectoryResult._get_packed_fingerprint():
            raise ValueError("Decode error")
        return FollowJointTrajectoryResult._decode_one(buf)

    @staticmethod
    def _decode_one(buf):
        self = FollowJointTrajectoryResult()
        self.status = core.ActionStatus._decode_one(buf)
        self.final_error, self.execution_time = struct.unpack(">dd", buf.read(16))
        return self

    @staticmethod
    def _get_hash_recursive(parents):
        if FollowJointTrajectoryResult in parents: return 0
        newparents = parents + [FollowJointTrajectoryResult]
        tmphash = (0x8ee9eef590c2e137+ core.ActionStatus._get_hash_recursive(newparents)) & 0xffffffffffffffff
        tmphash  = (((tmphash<<1)&0xffffffffffffffff) + (tmphash>>63)) & 0xffffffffffffffff
        return tmphash
    _packed_fingerprint = None

    @staticmethod
    def _get_packed_fingerprint():
        if FollowJointTrajectoryResult._packed_fingerprint is None:
            FollowJointTrajectoryResult._packed_fingerprint = struct.pack(">Q", FollowJointTrajectoryResult._get_hash_recursive([]))
        return FollowJointTrajectoryResult._packed_fingerprint

    def get_hash(self):
        """Get the LCM hash of the struct"""
        return struct.unpack(">Q", FollowJointTrajectoryResult._get_packed_fingerprint())[0]

