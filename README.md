# Tadaa -- 868 MHz Relay for Tado V3+ Smart Radiator Valves

Tado V3+ smart radiator valves communicate with a single Internet Bridge over 868 MHz using IEEE 802.15.4 / 6LoWPAN. The bridge has **no mesh or relay capability**. In multi-floor homes with thick walls, top-floor valves frequently lose connectivity.

**Tadaa** is a transparent 868 MHz relay that extends range by receiving and retransmitting Tado packets using a Raspberry Pi and a CC1101 radio module.

## How It Works

```
Valve (top floor)           Relay (stairway)          Bridge (ground floor)
      |                          |                          |
      |--- 868 MHz packet ------>|                          |
      |   (too weak for bridge)  |                          |
      |                          |-- retransmit (5-10ms) -->|
      |                          |                          |
      |                          |<-- bridge response ------|
      |<-- retransmit (5-10ms) --|                          |
```

The relay operates at the MAC layer -- it retransmits encrypted packets as-is without needing keys. The bridge and valves don't know a relay exists.

## Tado V3+ Radio Protocol (Reverse-Engineered)

This is the first public documentation of the Tado V3+ 868 MHz radio parameters:

| Parameter | Value |
|---|---|
| Frequency | 868.3 MHz |
| Modulation | GFSK (Gaussian Frequency Shift Keying) |
| Data rate | 38,400 baud |
| Deviation | 20 kHz |
| Sync word | `0x91D3` (CC1101 default `0xD391` byte-swapped) |
| Protocol | IEEE 802.15.4 / 6LoWPAN |
| Security | AES-CCM on ~52% of frames |
| ACK requests | ~10% of frames (relay-friendly) |
| Radio chip | TI CC110L (CC1101-compatible) |

### Frame Statistics (from a 2-minute capture)

- 35,103 packets received, 22,201 valid IEEE 802.15.4 frames (63%)
- Frame types: Beacon 45%, MAC Command 45%, Data 7%, ACK 3%
- Addressing: mix of 16-bit short and 64-bit extended IEEE addresses
- Inter-packet gap: 0.8ms min, 3.4ms avg, 34.8ms max

### Key Discovery: Sync Word

The Tado bridge uses the CC1101 default sync word `0xD391` but transmits it **byte-swapped** as `0x91D3`. This was discovered by probing 156 combinations of sync words, data rates, and modulations. The `tadaa-probe` tool automates this process.

## Recommended Hardware: CC1101 RPi Shield by Hallard

The easiest way to connect a CC1101 to a Raspberry Pi is the [CC1101 Mini Shield by Hallard](https://github.com/hallard/cc1101-e07-pi), which plugs directly onto the GPIO header -- no soldering or jumper wires needed.

**Buy it here:** [CC1101 Mini Shield on Tindie](https://www.tindie.com/products/hallard/cc1101-mini-shield-for-raspberry-pi/) (~$12)

> **Note:** The shield ships with a 433 MHz antenna by default. For Tado you need an **868 MHz** version or swap the antenna for an 868 MHz one.

Any CC1101 868 MHz SPI module will work -- the shield just makes wiring easier.

## Installation

### 1. Enable SPI

Add to `/boot/firmware/config.txt`:
```
dtparam=spi=on
```

### 2. Install

```bash
sudo mkdir -p /opt/tadaa
sudo chown $USER:$USER /opt/tadaa
cd /opt/tadaa
python3 -m venv venv
source venv/bin/activate
pip install .
```

### 3. Verify Hardware

```bash
# Check CC1101 is connected
python3 -c "
from tadaa.cc1101.driver import CC1101Driver
with CC1101Driver() as d:
    ver = d.read_status_register(0x31)
    print(f'CC1101 VERSION=0x{ver:02X}')  # Should be 0x14
"
```

## Usage

### Run as a Service

The simplest way to run the relay:

```bash
sudo cp deploy/tadaa-relay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tadaa-relay
```

This starts the relay at 868.3 MHz with an HTTP stats endpoint on port 8080. It auto-starts on boot and restarts on crash.

Monitor via the stats endpoint:

```bash
curl http://localhost:8080/stats
```

```json
{
  "uptime": "4h 12m 33s",
  "packets_relayed": 14823,
  "packets_dropped": 312,
  "last_packet_rssi": -67.5,
  "known_devices": ["3fcf", "f057", "1025", "..."],
  "errors": 0
}
```

### Advanced

#### Manual Relay

Start the relay manually (foreground):

```bash
tadaa-relay -f 868300000 --stats-port 8080
```

#### Frequency Scan

Find active 868 MHz channels:

```bash
tadaa-scan --start 868000000 --end 868600000 --step 25000
```

#### Auto-Detect Radio Config

Probe for the correct sync word, data rate, and modulation:

```bash
tadaa-probe -f 868300000 -d 5 -o probe_results.json
```

Change a temperature on the Tado app during the scan to generate radio traffic.

#### Packet Sniffer

Capture and decode IEEE 802.15.4 packets:

```bash
tadaa-sniff -f 868300000 -d 120 -o capture.jsonl
```

## Relay Design

- **Layer:** Raw IEEE 802.15.4 MAC frames -- no decryption needed
- **Deduplication:** 5-second sliding window using full packet bytes
- **TX jitter:** Random 5-10ms delay to avoid collision with the original
- **Direction:** Bidirectional (valve-to-bridge and bridge-to-valve)
- **ACK handling:** 90% of Tado frames don't request ACKs, so transparent relay works without ACK spoofing
- **Duty cycle:** Well within the EU 868 MHz 1% duty cycle limit

## Regulatory Notes

The 868.0-868.6 MHz band in the EU (SRD Band 48) has a **1% duty cycle limit**. The relay roughly doubles airtime per packet, but Tado's low traffic volume (valves report infrequently) keeps total duty cycle well under 1%.

## License

MIT
