"""
Read ECU identification from a VAG MED17.5 (Bosch) engine ECU over UDS/ISO15765,
using a J2534 pass-thru adapter (Topdon RLINK, Tactrix OpenPort 2.0, etc.) on Windows.

READ-ONLY. This script only sends UDS ReadDataByIdentifier (service 0x22) requests
and prints what comes back. It does not start a programming session, does not touch
security access, and never erases or writes any memory. It is safe to run on a car
with the engine off and ignition on.

Purpose: find out exactly which ECU and firmware you have (part number, software and
hardware versions, VIN, system name) so later decisions are based on fact.

Usage (Windows, from a terminal):
    python read_ecu_id.py                 # auto-discover the J2534 driver
    python read_ecu_id.py --list          # just list installed J2534 drivers
    python read_ecu_id.py --dll "C:\\path\\to\\driver.dll"

Put a battery maintainer on the car before any ECU session.
"""

import argparse
import sys

from j2534 import J2534, find_drivers, J2534Error

# Engine ECU on the diagnostic CAN bus (UDS physical addressing).
REQ_ID = 0x7E0
RESP_ID = 0x7E8

# UDS service IDs
SID_READ_DID = 0x22
NRC_RESPONSE_PENDING = 0x78

# Standard ASAM/UDS identification DIDs plus VW-specific ones. These are the
# values a tuning/diagnostic tool reads to recognise an ECU variant.
DIDS = [
    (0xF190, "VIN (ISO)"),
    (0xF187, "VW spare part number"),
    (0xF189, "VW application software version"),
    (0xF191, "VW ECU hardware number"),
    (0xF1A2, "VW application data identification"),
    (0xF18C, "ECU serial number"),
    (0xF197, "System name / ECU name"),
    (0xF18A, "System supplier identifier"),
    (0xF192, "VW ECU hardware version number"),
    (0xF193, "VW ECU hardware version"),
    (0xF195, "VW ECU software version"),
    (0xF1AA, "VW workshop system name"),
    (0x0600, "VW coding"),
]


def decode(payload):
    """Return (ascii, hex) renderings of a response payload."""
    hexs = payload.hex(" ")
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in payload)
    return text, hexs


def read_did(dev, did, timeout=1500):
    """Send ReadDataByIdentifier for one DID; return raw data bytes after the
    echoed DID, or None, or a ('NRC', code) tuple for a negative response."""
    req = bytes([SID_READ_DID, (did >> 8) & 0xFF, did & 0xFF])
    dev.write(REQ_ID, req)

    # The ECU may answer 0x7F .. 0x78 (response pending) a few times before the
    # real answer; loop past those.
    for _ in range(12):
        resp = dev.read_one(timeout=timeout)
        if resp is None:
            return None
        if len(resp) >= 3 and resp[0] == 0x7F:
            if resp[2] == NRC_RESPONSE_PENDING:
                continue
            return ("NRC", resp[2])
        if resp and resp[0] == (SID_READ_DID + 0x40):
            # positive: 0x62, DID hi, DID lo, data...
            return resp[3:]
        # Unrelated frame; keep looking briefly.
    return None


def main():
    ap = argparse.ArgumentParser(description="Read VAG MED17.5 ECU identification (read-only).")
    ap.add_argument("--dll", help="Path to J2534 driver DLL (default: auto-discover).")
    ap.add_argument("--list", action="store_true", help="List installed J2534 drivers and exit.")
    ap.add_argument("--req", default=hex(REQ_ID), help="Request CAN ID (default 0x7E0).")
    ap.add_argument("--resp", default=hex(RESP_ID), help="Response CAN ID (default 0x7E8).")
    args = ap.parse_args()

    drivers = find_drivers()
    if args.list:
        if not drivers:
            print("No J2534 v04.04 drivers found in the registry.")
        for name, dll in drivers:
            print(f"  {name}\n      {dll}")
        return 0

    dll = args.dll
    if not dll:
        if not drivers:
            print("No J2534 driver found. Install the Topdon RLINK driver, or pass --dll.",
                  file=sys.stderr)
            return 2
        # Prefer a Topdon/RLINK entry if present, else take the first.
        pick = next((d for d in drivers if "topdon" in d[0].lower() or "rlink" in d[0].lower()),
                    drivers[0])
        name, dll = pick
        print(f"Using J2534 driver: {name}\n  {dll}")

    req_id = int(args.req, 0)
    resp_id = int(args.resp, 0)

    try:
        with J2534(dll) as dev:
            dev.connect_iso15765(baud=500000)
            dev.add_flow_control_filter(req_id, resp_id)
            print(f"\nConnected. Querying ECU at request={hex(req_id)} response={hex(resp_id)}\n")
            print(f"{'DID':<8}{'Description':<36}{'Value'}")
            print("-" * 80)
            any_ok = False
            for did, desc in DIDS:
                try:
                    res = read_did(dev, did)
                except J2534Error as e:
                    print(f"0x{did:04X}  {desc:<34}  <error: {e}>")
                    continue
                if res is None:
                    print(f"0x{did:04X}  {desc:<34}  <no response>")
                elif isinstance(res, tuple) and res[0] == "NRC":
                    print(f"0x{did:04X}  {desc:<34}  <not supported, NRC 0x{res[1]:02X}>")
                else:
                    any_ok = True
                    text, hexs = decode(res)
                    print(f"0x{did:04X}  {desc:<34}  {text}")
                    print(f"{'':<8}{'':<36}[{hexs}]")
            print("-" * 80)
            if not any_ok:
                print("No DIDs answered. Check: ignition ON, correct CAN IDs, adapter wiring.")
            else:
                print("Done. Save this output — it identifies your exact ECU variant.")
    except J2534Error as e:
        print(f"J2534 error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Could not load driver DLL '{dll}': {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
