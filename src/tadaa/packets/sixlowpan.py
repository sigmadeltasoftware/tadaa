"""6LoWPAN dispatch header parser."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto


class DispatchType(Enum):
    IPV6 = auto()            # 01000001
    IPHC = auto()            # 011xxxxx
    MESH = auto()            # 10xxxxxx
    FRAG_FIRST = auto()      # 11000xxx
    FRAG_SUBSEQUENT = auto() # 11100xxx
    BROADCAST = auto()       # 01010000
    UNKNOWN = auto()


@dataclass
class SixLowPANHeader:
    dispatch_type: DispatchType
    dispatch_byte: int
    raw: bytes

    def summary(self) -> str:
        return f"6LoWPAN {self.dispatch_type.name} (0x{self.dispatch_byte:02X})"


def parse_dispatch(data: bytes) -> SixLowPANHeader:
    if len(data) == 0:
        raise ValueError("6LoWPAN data is empty")
    dispatch = data[0]
    if dispatch == 0x41:
        dtype = DispatchType.IPV6
    elif dispatch == 0x50:
        dtype = DispatchType.BROADCAST
    elif (dispatch & 0xE0) == 0x60:
        dtype = DispatchType.IPHC
    elif (dispatch & 0xC0) == 0x80:
        dtype = DispatchType.MESH
    elif (dispatch & 0xF8) == 0xC0:
        dtype = DispatchType.FRAG_FIRST
    elif (dispatch & 0xF8) == 0xE0:
        dtype = DispatchType.FRAG_SUBSEQUENT
    else:
        dtype = DispatchType.UNKNOWN
    return SixLowPANHeader(dispatch_type=dtype, dispatch_byte=dispatch, raw=data)
