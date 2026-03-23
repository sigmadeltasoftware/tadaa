"""IEEE 802.15.4 MAC frame parser."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class FrameType(IntEnum):
    BEACON = 0
    DATA = 1
    ACK = 2
    COMMAND = 3


class AddrMode(IntEnum):
    NONE = 0
    SHORT = 2
    LONG = 3


# Frame control field bit positions
_FC_FRAME_TYPE_MASK = 0x0007
_FC_SECURITY_ENABLED = 0x0008
_FC_FRAME_PENDING = 0x0010
_FC_ACK_REQUEST = 0x0020
_FC_PAN_ID_COMPRESSION = 0x0040
_FC_DEST_ADDR_MODE_SHIFT = 10
_FC_DEST_ADDR_MODE_MASK = 0x0C00
_FC_SRC_ADDR_MODE_SHIFT = 14
_FC_SRC_ADDR_MODE_MASK = 0xC000

_ADDR_LEN = {
    AddrMode.NONE: 0,
    AddrMode.SHORT: 2,
    AddrMode.LONG: 8,
}


@dataclass
class MACFrame:
    frame_type: FrameType
    security_enabled: bool
    frame_pending: bool
    ack_request: bool
    pan_id_compression: bool
    sequence_number: int
    dest_pan_id: Optional[int]
    dest_addr: Optional[bytes]
    src_pan_id: Optional[int]
    src_addr: Optional[bytes]
    payload: bytes
    raw: bytes

    def summary(self) -> str:
        parts = [self.frame_type.name]
        if self.dest_addr is not None:
            # Format as hex address (little-endian integer display)
            addr_int = int.from_bytes(self.dest_addr, "little")
            addr_hex = f"0x{addr_int:04x}"
            parts.append(f"dst={addr_hex}")
        if self.src_addr is not None:
            addr_int = int.from_bytes(self.src_addr, "little")
            addr_hex = f"0x{addr_int:04x}"
            parts.append(f"src={addr_hex}")
        if self.ack_request:
            parts.append("ACK_REQ")
        if self.security_enabled:
            parts.append("SEC")
        parts.append(f"seq={self.sequence_number}")
        return " | ".join(parts)


def parse_mac_frame(raw: bytes) -> MACFrame:
    """Parse an IEEE 802.15.4 MAC frame from raw bytes.

    Args:
        raw: Raw frame bytes (without PHY preamble/SFD/length).

    Returns:
        Parsed MACFrame.

    Raises:
        ValueError: If the frame is too short to be valid.
    """
    if len(raw) < 3:
        raise ValueError("Frame too short: need at least 3 bytes (FC + seq)")

    fc = struct.unpack_from("<H", raw, 0)[0]
    sequence_number = raw[2]
    offset = 3

    frame_type = FrameType(fc & _FC_FRAME_TYPE_MASK)
    security_enabled = bool(fc & _FC_SECURITY_ENABLED)
    frame_pending = bool(fc & _FC_FRAME_PENDING)
    ack_request = bool(fc & _FC_ACK_REQUEST)
    pan_id_compression = bool(fc & _FC_PAN_ID_COMPRESSION)

    dest_addr_mode = AddrMode((fc & _FC_DEST_ADDR_MODE_MASK) >> _FC_DEST_ADDR_MODE_SHIFT)
    src_addr_mode = AddrMode((fc & _FC_SRC_ADDR_MODE_MASK) >> _FC_SRC_ADDR_MODE_SHIFT)

    dest_pan_id: Optional[int] = None
    dest_addr: Optional[bytes] = None
    src_pan_id: Optional[int] = None
    src_addr: Optional[bytes] = None

    # Parse destination address fields
    if dest_addr_mode != AddrMode.NONE:
        if offset + 2 > len(raw):
            raise ValueError("Frame too short: missing destination PAN ID")
        dest_pan_id = struct.unpack_from("<H", raw, offset)[0]
        offset += 2

        dest_len = _ADDR_LEN[dest_addr_mode]
        if offset + dest_len > len(raw):
            raise ValueError("Frame too short: missing destination address")
        dest_addr = raw[offset: offset + dest_len]
        offset += dest_len

    # Parse source address fields
    if src_addr_mode != AddrMode.NONE:
        # PAN ID compression: src PAN ID is omitted when dest PAN ID is present
        if not pan_id_compression or dest_addr_mode == AddrMode.NONE:
            if offset + 2 > len(raw):
                raise ValueError("Frame too short: missing source PAN ID")
            src_pan_id = struct.unpack_from("<H", raw, offset)[0]
            offset += 2
        else:
            # Compressed: src PAN ID same as dest PAN ID
            src_pan_id = dest_pan_id

        src_len = _ADDR_LEN[src_addr_mode]
        if offset + src_len > len(raw):
            raise ValueError("Frame too short: missing source address")
        src_addr = raw[offset: offset + src_len]
        offset += src_len

    payload = raw[offset:]

    return MACFrame(
        frame_type=frame_type,
        security_enabled=security_enabled,
        frame_pending=frame_pending,
        ack_request=ack_request,
        pan_id_compression=pan_id_compression,
        sequence_number=sequence_number,
        dest_pan_id=dest_pan_id,
        dest_addr=dest_addr,
        src_pan_id=src_pan_id,
        src_addr=src_addr,
        payload=payload,
        raw=raw,
    )
