"""LCM type definitions
This file automatically generated by lcm.
DO NOT MODIFY BY HAND!!!!
"""


from io import BytesIO
import struct

import core

class UInt64Response(object):

    __slots__ = ["response_header", "result"]

    __typenames__ = ["core.ResponseHeader", "int64_t"]

    __dimensions__ = [None, None]

    def __init__(self):
        self.response_header = core.ResponseHeader()
        """ LCM Type: core.ResponseHeader """
        self.result = 0
        """ LCM Type: int64_t """

    def encode(self):
        buf = BytesIO()
        buf.write(UInt64Response._get_packed_fingerprint())
        self._encode_one(buf)
        return buf.getvalue()

    def _encode_one(self, buf):
        assert self.response_header._get_packed_fingerprint() == core.ResponseHeader._get_packed_fingerprint()
        self.response_header._encode_one(buf)
        buf.write(struct.pack(">q", self.result))

    @staticmethod
    def decode(data: bytes):
        if hasattr(data, 'read'):
            buf = data
        else:
            buf = BytesIO(data)
        if buf.read(8) != UInt64Response._get_packed_fingerprint():
            raise ValueError("Decode error")
        return UInt64Response._decode_one(buf)

    @staticmethod
    def _decode_one(buf):
        self = UInt64Response()
        self.response_header = core.ResponseHeader._decode_one(buf)
        self.result = struct.unpack(">q", buf.read(8))[0]
        return self

    @staticmethod
    def _get_hash_recursive(parents):
        if UInt64Response in parents: return 0
        newparents = parents + [UInt64Response]
        tmphash = (0x6ce08879530b5aeb+ core.ResponseHeader._get_hash_recursive(newparents)) & 0xffffffffffffffff
        tmphash  = (((tmphash<<1)&0xffffffffffffffff) + (tmphash>>63)) & 0xffffffffffffffff
        return tmphash
    _packed_fingerprint = None

    @staticmethod
    def _get_packed_fingerprint():
        if UInt64Response._packed_fingerprint is None:
            UInt64Response._packed_fingerprint = struct.pack(">Q", UInt64Response._get_hash_recursive([]))
        return UInt64Response._packed_fingerprint

    def get_hash(self):
        """Get the LCM hash of the struct"""
        return struct.unpack(">Q", UInt64Response._get_packed_fingerprint())[0]

