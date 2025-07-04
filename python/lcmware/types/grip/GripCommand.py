"""LCM type definitions
This file automatically generated by lcm.
DO NOT MODIFY BY HAND!!!!
"""


from io import BytesIO
import struct

import core

class GripCommand(object):

    __slots__ = ["header", "position", "speed", "force"]

    __typenames__ = ["core.Header", "float", "float", "float"]

    __dimensions__ = [None, None, None, None]

    def __init__(self):
        self.header = core.Header()
        """ LCM Type: core.Header """
        self.position = 0.0
        """ LCM Type: float """
        self.speed = 0.0
        """ LCM Type: float """
        self.force = 0.0
        """ LCM Type: float """

    def encode(self):
        buf = BytesIO()
        buf.write(GripCommand._get_packed_fingerprint())
        self._encode_one(buf)
        return buf.getvalue()

    def _encode_one(self, buf):
        assert self.header._get_packed_fingerprint() == core.Header._get_packed_fingerprint()
        self.header._encode_one(buf)
        buf.write(struct.pack(">fff", self.position, self.speed, self.force))

    @staticmethod
    def decode(data: bytes):
        if hasattr(data, 'read'):
            buf = data
        else:
            buf = BytesIO(data)
        if buf.read(8) != GripCommand._get_packed_fingerprint():
            raise ValueError("Decode error")
        return GripCommand._decode_one(buf)

    @staticmethod
    def _decode_one(buf):
        self = GripCommand()
        self.header = core.Header._decode_one(buf)
        self.position, self.speed, self.force = struct.unpack(">fff", buf.read(12))
        return self

    @staticmethod
    def _get_hash_recursive(parents):
        if GripCommand in parents: return 0
        newparents = parents + [GripCommand]
        tmphash = (0xc2e54379d3cca894+ core.Header._get_hash_recursive(newparents)) & 0xffffffffffffffff
        tmphash  = (((tmphash<<1)&0xffffffffffffffff) + (tmphash>>63)) & 0xffffffffffffffff
        return tmphash
    _packed_fingerprint = None

    @staticmethod
    def _get_packed_fingerprint():
        if GripCommand._packed_fingerprint is None:
            GripCommand._packed_fingerprint = struct.pack(">Q", GripCommand._get_hash_recursive([]))
        return GripCommand._packed_fingerprint

    def get_hash(self):
        """Get the LCM hash of the struct"""
        return struct.unpack(">Q", GripCommand._get_packed_fingerprint())[0]

