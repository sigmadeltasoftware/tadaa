"""CLI entry points for tadaa: scan, sniff, relay, and probe."""

from __future__ import annotations

import argparse
import sys
import threading


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

def scan(argv: list[str] | None = None) -> None:
    """Frequency sweep entry point (tadaa-scan)."""
    parser = argparse.ArgumentParser(
        prog="tadaa-scan",
        description="Sweep a range of frequencies and display RSSI at each step.",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=863_000_000,
        metavar="HZ",
        help="Start frequency in Hz (default: 863000000)",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=870_000_000,
        metavar="HZ",
        help="End frequency in Hz (default: 870000000)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=100_000,
        metavar="HZ",
        help="Step size in Hz (default: 100000)",
    )
    parser.add_argument(
        "--dwell",
        type=float,
        default=0.005,
        metavar="S",
        help="Dwell time per frequency in seconds (default: 0.005)",
    )
    parser.add_argument(
        "--spi-bus",
        type=int,
        default=0,
        metavar="N",
        help="SPI bus number (default: 0)",
    )
    parser.add_argument(
        "--spi-cs",
        type=int,
        default=0,
        metavar="N",
        help="SPI chip-select number (default: 0)",
    )

    args = parser.parse_args(argv)

    from tadaa.cc1101.driver import CC1101Driver
    from tadaa.sniffer.scanner import FrequencyScanner

    with CC1101Driver(bus=args.spi_bus, device=args.spi_cs) as driver:
        scanner = FrequencyScanner(driver)
        print(f"{'Frequency (MHz)':>18}  {'RSSI (dBm)':>10}  Signal")
        print("-" * 50)
        results = scanner.scan(
            start_hz=args.start,
            end_hz=args.end,
            step_hz=args.step,
            dwell_s=args.dwell,
        )
        for r in results:
            bar_len = max(0, min(30, int((r.rssi_dbm + 110) * 30 / 60)))
            bar = "#" * bar_len
            print(f"{r.frequency_hz / 1e6:>18.3f}  {r.rssi_dbm:>10.1f}  {bar}")

        if results:
            peak = FrequencyScanner.find_peak(results)
            print()
            print(
                f"Peak: {peak.frequency_hz / 1e6:.3f} MHz  "
                f"RSSI={peak.rssi_dbm:.1f} dBm"
            )


# ---------------------------------------------------------------------------
# sniff
# ---------------------------------------------------------------------------

def sniff(argv: list[str] | None = None) -> None:
    """Packet capture entry point (tadaa-sniff)."""
    parser = argparse.ArgumentParser(
        prog="tadaa-sniff",
        description="Capture IEEE 802.15.4 packets on the specified frequency.",
    )
    parser.add_argument(
        "-f", "--frequency",
        type=int,
        required=True,
        metavar="HZ",
        help="Carrier frequency in Hz (e.g. 868300000)",
    )
    parser.add_argument(
        "-d", "--duration",
        type=float,
        default=60.0,
        metavar="S",
        help="Capture duration in seconds (default: 60)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write captured packets to FILE as JSON lines",
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        metavar="NAME",
        help="Radio config preset name (see SCAN_CONFIGS; default: tado_primary_gfsk_38k4)",
    )
    parser.add_argument(
        "--spi-bus",
        type=int,
        default=0,
        metavar="N",
        help="SPI bus number (default: 0)",
    )
    parser.add_argument(
        "--spi-cs",
        type=int,
        default=0,
        metavar="N",
        help="SPI chip-select number (default: 0)",
    )

    args = parser.parse_args(argv)

    from pathlib import Path
    from tadaa.cc1101.driver import CC1101Driver
    from tadaa.cc1101.config import SCAN_CONFIGS, RadioConfig
    from tadaa.sniffer.capture import PacketCapture
    from tadaa.sniffer.analyzer import TrafficAnalyzer

    radio_cfg: RadioConfig | None = None
    if args.config is not None:
        for cfg in SCAN_CONFIGS:
            if cfg.name == args.config:
                radio_cfg = cfg
                break
        if radio_cfg is None:
            print(
                f"Unknown config preset '{args.config}'. "
                f"Available: {[c.name for c in SCAN_CONFIGS]}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        base = SCAN_CONFIGS[0]
        radio_cfg = RadioConfig(
            name=base.name,
            frequency_hz=args.frequency,
            data_rate_baud=base.data_rate_baud,
            modulation=base.modulation,
            deviation_hz=base.deviation_hz,
            sync_word=base.sync_word,
            bandwidth_khz=base.bandwidth_khz,
        )

    log_path = Path(args.output) if args.output else None

    print(
        f"Sniffing {args.frequency / 1e6:.3f} MHz "
        f"for {args.duration:.0f}s ..."
    )

    with CC1101Driver(bus=args.spi_bus, device=args.spi_cs) as driver:
        capture = PacketCapture(driver, radio_cfg)
        packets = capture.run(duration_s=args.duration, log_path=log_path)

    print(f"Captured {len(packets)} packet(s).")

    if packets:
        analyzer = TrafficAnalyzer(packets)
        report = analyzer.analyze()
        print(report.summary())

    if args.output:
        print(f"Log written to {args.output}")


# ---------------------------------------------------------------------------
# relay
# ---------------------------------------------------------------------------

def relay(argv: list[str] | None = None) -> None:
    """Relay daemon entry point (tadaa-relay)."""
    parser = argparse.ArgumentParser(
        prog="tadaa-relay",
        description="Receive, deduplicate, and retransmit 868 MHz packets.",
    )
    parser.add_argument(
        "-f", "--frequency",
        type=int,
        required=True,
        metavar="HZ",
        help="Carrier frequency in Hz (e.g. 868300000)",
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        metavar="NAME",
        help="Radio config preset name (default: tado_primary_gfsk_38k4)",
    )
    parser.add_argument(
        "--stats-port",
        type=int,
        default=8080,
        metavar="PORT",
        help="TCP port for the HTTP stats server (default: 8080)",
    )
    parser.add_argument(
        "--spi-bus",
        type=int,
        default=0,
        metavar="N",
        help="SPI bus number (default: 0)",
    )
    parser.add_argument(
        "--spi-cs",
        type=int,
        default=0,
        metavar="N",
        help="SPI chip-select number (default: 0)",
    )

    args = parser.parse_args(argv)

    import asyncio
    import logging
    from tadaa.cc1101.driver import CC1101Driver
    from tadaa.cc1101.config import SCAN_CONFIGS, RadioConfig
    from tadaa.relay.daemon import RelayDaemon
    from tadaa.relay.stats import create_stats_app
    from aiohttp import web

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    radio_cfg: RadioConfig | None = None
    if args.config is not None:
        for cfg in SCAN_CONFIGS:
            if cfg.name == args.config:
                radio_cfg = cfg
                break
        if radio_cfg is None:
            print(
                f"Unknown config preset '{args.config}'. "
                f"Available: {[c.name for c in SCAN_CONFIGS]}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        base = SCAN_CONFIGS[0]
        radio_cfg = RadioConfig(
            name=base.name,
            frequency_hz=args.frequency,
            data_rate_baud=base.data_rate_baud,
            modulation=base.modulation,
            deviation_hz=base.deviation_hz,
            sync_word=base.sync_word,
            bandwidth_khz=base.bandwidth_khz,
        )

    with CC1101Driver(bus=args.spi_bus, device=args.spi_cs) as driver:
        daemon = RelayDaemon(driver=driver, config=radio_cfg)

        app = create_stats_app(daemon.stats)

        def _run_stats_server() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            runner = web.AppRunner(app)
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, "0.0.0.0", args.stats_port)
            loop.run_until_complete(site.start())
            loop.run_forever()

        stats_thread = threading.Thread(
            target=_run_stats_server,
            daemon=True,
            name="stats-server",
        )
        stats_thread.start()

        print(
            f"Relay daemon starting at {args.frequency / 1e6:.3f} MHz "
            f"(stats on :{args.stats_port})"
        )
        daemon.run()


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------

def probe(argv: list[str] | None = None) -> None:
    """Radio config probe entry point (tadaa-probe)."""
    parser = argparse.ArgumentParser(
        prog="tadaa-probe",
        description="Try many sync words and data rates to find the correct radio config.",
    )
    parser.add_argument(
        "-f", "--frequency",
        type=int,
        default=868_300_000,
        metavar="HZ",
        help="Carrier frequency in Hz (default: 868300000)",
    )
    parser.add_argument(
        "-d", "--duration",
        type=float,
        default=5.0,
        metavar="S",
        help="Dwell time per configuration in seconds (default: 5)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write results to FILE as JSON",
    )
    parser.add_argument(
        "--spi-bus",
        type=int,
        default=0,
        metavar="N",
        help="SPI bus number (default: 0)",
    )
    parser.add_argument(
        "--spi-cs",
        type=int,
        default=0,
        metavar="N",
        help="SPI chip-select number (default: 0)",
    )

    args = parser.parse_args(argv)

    import json
    from pathlib import Path
    from tadaa.cc1101.driver import CC1101Driver
    from tadaa.sniffer.probe import probe as run_probe

    print(
        f"Probing {args.frequency / 1e6:.3f} MHz -- "
        f"{args.duration:.0f}s per config, ~{13 * 6 * 2 * args.duration / 60:.0f} min total"
    )
    print("Trigger Tado activity (change a temperature) during this scan!")
    print()

    with CC1101Driver(bus=args.spi_bus, device=args.spi_cs) as driver:
        results = run_probe(
            driver,
            frequency_hz=args.frequency,
            duration_per_config_s=args.duration,
        )

    valid = [r for r in results if r["valid_802154"] > 0]
    print()
    if valid:
        print(f"=== FOUND {len(valid)} config(s) with valid 802.15.4 frames ===")
        for v in valid:
            print(
                f"  sync={v['sync_word']} ({v['sync_name']}) "
                f"rate={v['data_rate']} {v['modulation']} "
                f"=> {v['valid_802154']} valid frames"
            )
            for f in v["frames"][:3]:
                print(f"    {f['parsed']['frame_type']} seq={f['parsed']['seq_num']} "
                      f"RSSI={f['rssi_dbm']:.1f} len={f['length']} {f['hex'][:60]}")
    else:
        print("No valid 802.15.4 frames found with any configuration.")
        print("Try: different frequency, longer dwell time, or ensure Tado is active.")

    if args.output:
        with open(args.output, "w") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nFull results written to {args.output}")
