# A3 8P CBFA — ECU identity & P2568 delete plan

## Vehicle
- 2012 Audi A3 (8P), VIN starts `WAUBEAFMXCA05…`
- Engine: **CBFA** 2.0 TFSI (California PZEV)
- Current tune: Unitronic Stage 2+ (OBD-flashed via Unitronic's own cable → ECU is OBD read/write capable)

## ECU identity (confirmed from VCDS + Mode 09 + firmware listings)
| Field | Value |
|---|---|
| VAG number | `8P0 907 115 BC` |
| Component | `2.0l R4/4V TFSI` |
| Calibration | `0020` (Mode 09 Cal ID: `8P0907115BC 0020`) |
| CVN | `23D4E4A9` (checksum of currently loaded cal — may be non-stock if tuned) |
| Platform | **Bosch MED17.1** |
| Microcontroller | Infineon **TC1796** |
| Bosch number | `0261S06946` |
| Bosch flashware / SW number | `1037555451` (confirm via VCDS Advanced ID - 1A) |
| VCDS label file | `06J-907-115-CBF.CLB` |

### Still to confirm (VCDS `Advanced ID - 1A`, next time at car)
- Exact hardware number + software/ASAM dataset version straight from the ECU
- Confirms Bosch number `0261S06946` and flashware `1037555451`

## Target
Disable DTC **P2568** — "Sensor for Ozone Reducing Radiator Identification:
Implausible Signal" (G611 radiator-ID sensor on the PZEV PremAir radiator).
Orphaned because an aftermarket radiator without G611 is fitted. Track-only car,
not emissions tested. Pure emissions-compliance monitor; no effect on how the
engine runs.

## Approach
Disable the specific **DFC (Diagnostic Fault Check)** for the G611 check in the
calibration via the DSM (Diagnostic System Manager) config — do NOT erase tables.
Surgical and reversible. Checksum-correct on write.

## Tooling
- **Flasher:** PCMFlash **Module 71** (VAG MED17/EDC17). MED17.1 is OBD read/write
  capable (bench/boot as fallback if TPROT blocks OBD).
- **Map editor:** WinOLS (or similar) + an **A2L/damos for flashware `1037555451`**
  for named parameters. Without it, pattern-match the DFC flag.
- **Adapter:** proven options are Tactrix OpenPort 2.0 or Scanmatik 2 Pro.
  On-hand Topdon RLINK / Launch SmartLink C are J2534 but UNVERIFIED for PCMFlash —
  use a proven adapter for the WRITE step.

## Safety / brick-avoidance
- Battery maintainer on the car for ANY session.
- Full backup of flash **and** EEPROM before any write; verify it reads back clean.
- MED17 OBD writes can brick if interrupted — use a reliable adapter, stable power.
- Keep the edit minimal (just the P2568 DFC); let the tool recompute checksums.

## Status / next steps
1. [ ] VCDS `Advanced ID - 1A` screenshot → lock exact SW/flashware version.
2. [ ] Run `read_ecu_id.py` at the car (read-only) to capture current (tuned) IDs.
3. [ ] Confirm PCMFlash Module 71 lists `8P0907115BC 0020` / flashware `1037555451`.
4. [ ] Source an A2L/damos for `1037555451`.
5. [ ] Decide write adapter (lean OpenPort 2.0 / Scanmatik over RLINK/SmartLink).
6. [ ] Full backup (flash + EEPROM), verify.
7. [ ] Edit P2568 DFC, checksum-correct, write, verify, clear code.
