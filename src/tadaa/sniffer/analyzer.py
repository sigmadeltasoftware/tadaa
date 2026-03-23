"""Traffic analyzer: parse captured packets and produce a summary report."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Set

from tadaa.packets.ieee802154 import FrameType, parse_mac_frame
from tadaa.sniffer.capture import CapturedPacket


@dataclass
class TrafficReport:
    """Statistical summary of a captured packet buffer.

    All timing fields are in milliseconds.
    """

    total_packets: int = 0
    data_frames: int = 0
    ack_frames: int = 0

    #: True if any DATA frame has the ACK_REQUEST flag set.
    uses_mac_acks: bool = False

    #: True if any frame has the security-enabled bit set.
    security_enabled: bool = False

    #: Set of raw address bytes seen (destination and source combined).
    unique_addresses: Set[bytes] = field(default_factory=set)

    #: Set of PAN IDs seen (as integers).
    pan_ids: Set[int] = field(default_factory=set)

    min_inter_packet_ms: float = 0.0
    avg_inter_packet_ms: float = 0.0
    max_inter_packet_ms: float = 0.0

    avg_rssi_dbm: float = 0.0

    #: Number of packets that could not be parsed as valid MAC frames.
    parse_errors: int = 0

    def summary(self) -> str:
        """Return a human-readable one-line summary of the report."""
        parts = [
            f"total={self.total_packets}",
            f"data={self.data_frames}",
            f"ack_frames={self.ack_frames}",
            f"errors={self.parse_errors}",
            f"uses_acks={self.uses_mac_acks}",
            f"security={self.security_enabled}",
            f"unique_addrs={len(self.unique_addresses)}",
            f"pan_ids={len(self.pan_ids)}",
            f"avg_rssi={self.avg_rssi_dbm:.1f}dBm",
        ]
        if self.total_packets > 1:
            parts.append(
                f"ipg_min/avg/max={self.min_inter_packet_ms:.1f}/"
                f"{self.avg_inter_packet_ms:.1f}/{self.max_inter_packet_ms:.1f}ms"
            )
        return " | ".join(parts)


class TrafficAnalyzer:
    """Analyze a list of :class:`~tadaa.sniffer.capture.CapturedPacket` objects.

    Parameters
    ----------
    packets:
        Packet buffer to analyze.  Packets are expected to be in
        chronological order (ascending timestamp).
    """

    def __init__(self, packets: List[CapturedPacket]) -> None:
        self._packets = packets

    def analyze(self) -> TrafficReport:
        """Parse every packet and compute aggregate statistics.

        Returns
        -------
        TrafficReport
            Populated report; all fields are zero/empty if *packets* is empty.
        """
        report = TrafficReport()

        if not self._packets:
            return report

        report.total_packets = len(self._packets)

        rssi_sum = 0.0
        timestamps: list[float] = []

        for pkt in self._packets:
            rssi_sum += pkt.rssi_dbm
            timestamps.append(pkt.timestamp)

            try:
                frame = parse_mac_frame(pkt.raw)
            except (ValueError, Exception):
                report.parse_errors += 1
                continue

            # Frame-type counts
            if frame.frame_type == FrameType.DATA:
                report.data_frames += 1
            elif frame.frame_type == FrameType.ACK:
                report.ack_frames += 1

            # ACK-request flag
            if frame.ack_request:
                report.uses_mac_acks = True

            # Security
            if frame.security_enabled:
                report.security_enabled = True

            # Addresses
            if frame.dest_addr is not None:
                report.unique_addresses.add(bytes(frame.dest_addr))
            if frame.src_addr is not None:
                report.unique_addresses.add(bytes(frame.src_addr))

            # PAN IDs
            if frame.dest_pan_id is not None:
                report.pan_ids.add(frame.dest_pan_id)
            if frame.src_pan_id is not None:
                report.pan_ids.add(frame.src_pan_id)

        # Average RSSI
        report.avg_rssi_dbm = rssi_sum / len(self._packets)

        # Inter-packet gaps (milliseconds)
        if len(timestamps) > 1:
            gaps_ms = [
                (timestamps[i + 1] - timestamps[i]) * 1000.0
                for i in range(len(timestamps) - 1)
            ]
            report.min_inter_packet_ms = min(gaps_ms)
            report.max_inter_packet_ms = max(gaps_ms)
            report.avg_inter_packet_ms = sum(gaps_ms) / len(gaps_ms)

        return report
