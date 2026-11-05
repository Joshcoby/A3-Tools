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
| Bosch flashware / SW number | `1037555451` |
| Hardware part number | `8P0907115AL` (confirmed on ECU — matches firmware listing) |
| Hardware version | `E3H` |
| ECU protocol | **`KWP2000 CAN TP2.0`** (NOT UDS) |
| Software (long) coding | `010301081C070160` |
| VCDS label file | `06J-907-115-CBF.CLB` |

### Identity confirmed
HW `8P0907115AL` + SW `8P0907115BC` + `0020` is an exact match to the firmware
listing `0261S06946 / MED17.1 / 1037555451 / PCMFlash`. No ambiguity left.

### Protocol implication (important)
ECU speaks **KWP2000 CAN TP2.0**, not UDS. For PCMFlash the correct module is
**Module 65 (VAG MED17/EDC17 CAN TP2.0/K-Line)** — NOT 48 (UDS) and NOT 71 (bench).
TP2.0 also means an OBD **full read** may be limited (write-only / virtual-read on
some MED17.1); a guaranteed full read could require bench. Write over OBD works
(Unitronic flashed this way). READ feasibility over OBD is the open question.

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

## Adapter decision
- Options on hand: Topdon RLINK, Launch SmartLink C V2.0 (both J2534, PCMFlash
  support unverified).
- Genuine Tactrix OpenPort 2.0: out of stock / discontinued as of 2026.
- **Clone OpenPort 2.0** (e.g. Washinglee "K-CAN", ~$70 on Amazon) is a viable
  cheap option. Multiple reviewers confirm it is a faithful 1:1 Tactrix clone.
  - **CRITICAL: install the genuine Tactrix J2534 drivers from tactrix.com —
    NOT the seller's drivers/link.** With genuine drivers it presents to Windows
    as a real OpenPort 2.0, so PCMFlash recognizes it as a supported adapter.
  - Wipe any old J2534 driver installs first (EcuFlash/EvoScan etc.) so Windows
    binds the Tactrix driver.
  - Reviewers report flashing 20+ revisions with no drops/bricking — acceptable
    for the write, with the usual power precautions.

## PCMFlash read test — DO THIS FIRST (non-destructive, gates everything)
This single test answers three questions at once: (a) does PCMFlash recognize
the cable, (b) does the ECU read over OBD, (c) did Unitronic lock/protect the file.
1. Windows: install PCMFlash + Module 71 (VAG MED17/EDC17); install genuine
   Tactrix J2534 drivers if using the clone cable.
2. Battery maintainer on the car. Ignition ON, engine off.
3. Cable into OBD; in PCMFlash select the J2534 device and Module 71 / MED17.1.
4. Choose **READ** (identification first, then full read). Do NOT write anything.
5. Save the dump. Note exact file size.

### Interpreting the read
- **Good read:** expected size for TC1796 flash; contains readable ASCII
  (`8P0907115BC`, ASAM strings); recognizable low-entropy map/structure regions.
  → proceed to A2L + edits.
- **Bad read — diagnose before assuming the worst (upload dump for analysis):**
  - Wrong/short size → partial read (adapter/comms issue, retry/settings).
  - Tool "not recognized"/checksum mismatch → often config, usually solvable.
  - High-entropy noise throughout → actually protected/encrypted.
  - True hardware read-lock → fallback is bench/boot read (bypasses OBD lock).
- MED17.1 is NOT OEM-encrypted; a clean read is the most likely outcome.

## Practice-first bench plan (spare ECM)
Have a spare ECM from a 2012 GTI (CCTA). Use it to learn the full bench
read/edit/write/recover cycle at ZERO risk before touching the car's tuned ECU.
- **Confirm it's a practice twin:** get the spare's part number + Bosch `0 261 ...`
  number. A Mk6 Golf 2.0T MED17.1 may share Bosch `0261S06946` with our ECU
  (the firmware listing paired a Golf MK6 with `0261S06946`). If same
  MED17.1/TC1796/TP2.0 → identical bench pinout & procedure.
- **What transfers:** bench wiring, read, edit, write, recovery, tool validation.
- **What does NOT:** CCTA is non-PZEV, so NO G611/P2568 in its firmware — can't
  practice that exact DTC; mechanics still transfer. Locate `0x2568` on the real
  CBFA dump later.
- **Immo irrelevant for practice** (not starting an engine on the bench). Spare
  could also sandbox the immo-off procedure later.

### Sequence
1. Get spare's part/Bosch number → confirm MED17.1/TC1796 match.
2. Buy bench tool (see below).
3. Practice full read/edit/write/recover on the spare until confident.
4. Then pull the car's ECU and do it for real.

## Bench read: connectors first, open only if needed
- **Bench mode = connect at the ECU harness connectors** (power/ground/CAN/
  bench-enable per the tool's pinout). NO opening the case. Try this FIRST.
  Works on many MED17.1/17.1.1.
- **Boot mode = open the case.** Only if bench fails (updated/high-TPROT units).
  More invasive + a tool-guided password step. Riskier.
- Won't know which yours needs until tried (TPROT-dependent).
- Safety: bench = no solder, careful wiring + correct 12V, reversible. Boot =
  higher skill, higher brick risk.

## Bench tool: FoxFlash vs KT200
| | FoxFlash | KT200 |
|---|---|---|
| Price | ~$675 (full, all protocols) | Auto ~$535 / Full ~$705+ |
| Boot mode | included | needs Full version |
| Offline | native | needs internet / offline dongle |
| Warranty | 2 yr | 1 yr |
- **Pick: FoxFlash** — boot included, offline, longer warranty, strong on MED17.
  Need boot as fallback for high-TPROT. KT200 Auto cheaper but may lack boot.
- Buy genuine from a reputable seller — clones of both exist and can brick a unit.
- NOTE: the OpenPort cannot do bench/boot — it's for the OBD write path only.

## KT200 compatibility — CONFIRMED (from ECUHELP official support list)
- `Audi A3 1.8/2.0l TFSI, Bosch MED17` → **R/W, OBD** (listed).
- `Audi ALL, Bosch EDC/MED17` → **R/W, BOOT** (fallback, listed).
- Implication: genuine KT200 can R/W our ECU; OBD read may work (more than
  PCMFlash Module 65's write-only), with BOOT R/W as the guaranteed fallback for
  high-TPROT. Practice unit reveals which mode actually works.
- Caveat: list is generic "MED17", not "MED17.1 TC1796" specifically; TPROT may
  still force boot. Either way the tool covers it.
- BUY GENUINE (~$580-880, ECUHELP shop / authorized reseller). The $309 AliExpress
  "Full" unit is far below genuine pricing = almost certainly a clone (brick risk
  on writes). Support list applies to genuine hardware only.

## OpenPort OBD read — CONFIRMED NOT VIABLE for this ECU
- Direct report: genuine OpenPort 2.0 + PCMFlash on a MED17 TP2.0 ECU = read/write
  buttons GREYED OUT; PCMFlash needs a compatible bench device (Scanmatik) to
  enable reading. "With OpenPort you cannot." (MHH thread.)
- Virtual read exists for MED17.1 2.0T in PCMFlash/Autotuner lists BUT: needs a
  compatible device (not OpenPort per report) + a server-side DB entry for the
  exact file; murky/unreliable as a backup base for a TUNED car.
- Conclusion: the full backup READ needs BENCH/BOOT (KT200/FoxFlash). OpenPort
  cannot be the read tool.
- OpenPort still usable for the OBD WRITE (PCMFlash Module 65) if avoiding pulling
  the ECU for each write — but KT200 writes too, so OpenPort is optional.

## PRIMARY PLAN (budget): Ktag clone + spare CBFA ECM
Have a SECOND, IDENTICAL CBFA ECM (original, needs a sensor-ground re-solder).
Same unit = identical firmware incl. P2568/G611 + EVAP + TPROT. Ideal practice/dev
twin, and it's already being opened (boot-mode access is natural).

### Tool: Ktag clone (~$50-100) — confirmed does MED17.1 TC1796 (bench/boot)
Verify before buying:
- Firmware **7.020** (red PCB generation).
- **MASTER** version (not Slave/token-limited).
- Ships with a working **Ksuite 2.23 or 2.25**.
- NEVER update Ksuite online — it kills clone function. Install provided ver, offline.
- Includes TriCore bench/boot cables for MED17.1.
Caveats: KTAG is BENCH/BOOT only (NO OBD) → MED17.1 = boot mode = OPEN the ECU.
Fiddlier than KT200 but ~$250 cheaper. Clone quality varies (validate on spare).

### Workflow
1. Buy Ktag 7.020 Master clone; get right Ksuite working offline.
2. Repair + practice on spare CBFA: read it (bonus: genuine OEM CBFA stock file),
   practice edit/write/recover on IDENTICAL firmware, locate 0x2568 for real.
3. Then car's tuned ECM: read (backup), edit P2568/EVAP, write back, verify.

### Cost comparison
- Ktag clone + spare: ~$50-100 (this plan)
- KT200 clone: ~$309 (easier, solder-free, but clone write risk)
- Genuine KT200: ~$580-880 (safest, user declined)
- OpenPort OBD read: NOT viable (confirmed). OpenPort = optional OBD write only.

## Ktag clone — this listing CONFIRMED good combo
- Hardware V7.020 + Software Ksuite V2.25 = correct pairing (verified on listing).
- Master version.
- **Windows caveat:** Ksuite 2.25 supports Windows XP/7/8 — NOT Win10/11 (driver
  signature issues). Plan a dedicated Win7 laptop or a Win7 VM (USB passthrough).
- Still: never update Ksuite online; bench/boot only (no OBD).

## Ktag clone setup — "External exception EEFFACE" (common, fixable)
This is THE most common KESS/KTAG clone error — software/driver/environment, not
a dead tool. Fixes (do these proactively):
1. Run on **Windows 7** (not 10/11) — error strongly tied to newer Windows.
2. Clean driver install: uninstall "USB device" in Device Manager → unplug →
   install bundled **USBDEVICEDRV** driver → replug → run Ksuite with internet OFF.
3. Add **antivirus/Defender exception** for the Ksuite folder (clones trip AV).
4. Reseat/clean the internal **SD/TF card** (holds the program).
5. Keep **offline** always; never update Ksuite online.
WARNING: do NOT download "fixed" Ksuite ISOs/drivers from file-sharing links
(malware risk). Use only the seller-provided install media.

## Open-source alternatives (free, researched 2026-11-05)
Found via GitHub search after exhausting commercial damos marketplaces (no exact-match
A2L/damos exists publicly for 8P0907115BC/1037555451 — confirmed via direct internal
search on AutomaticTuningFiles, ecufix.info, and ecusoft.ru, all zero results).

### ECU-Studio-AI (PCTestAdmin) — https://github.com/PCTestAdmin/ECU-Studio-AI
- Free, open source, GPL-3.0, Windows, Python 3.10-3.13 (no Python install needed to run).
- **Finds calibration maps WITHOUT a pre-existing definition** — code-reference analysis
  (TriCore supported), record-header/axis structure analysis, data-pattern heuristics.
  Grades each find by evidence type (code/structure/pattern), not invented percentages.
- Supports importing TunerPro XDF, ASAM A2L/DAMOS (with EPK check), RomRaider XML, CSV
  if we ever get one.
- ORI/MOD (stock vs modified) compare, checksum verify/correct, hex/table/heatmap/3D views.
  Never edits the original file.
- **IMPORTANT CAVEAT (from their own README):** "Deliberately out of scope: automatic
  'stage 1' tuning, disabling emission or protection functions, flash approval." The dev
  has intentionally excluded automated emissions-disable workflows. Still useful as a
  general structure/map finder — we'd identify + make the actual edit ourselves.
- Support matrix: docs/ECU_SUPPORT.md (check for MED17.1 specifically before relying on it;
  measured results shown for EDC17CP09 and Siemens MSD85 in the README, not MED17.1).

### VAGFlasher (dspl1236/osmikejarden) — https://github.com/dspl1236/VAGFlasher
- Free, open source, MIT license. "No cloud. No subscriptions. No phone-home."
- Works with existing J2534 cable (OpenPort) or a cheap ESP32 "FunkBridge" dongle.
- Has real UDS + SA2 seed/key protocol implementation.
- **Current support table does NOT include MED17.1** (our ECU):
  - ME17.5 (MED17.5) EA888 Gen1/1.5 CCTA/CCZA — done (Milestone 1)
  - ME17.5.2 — done (Milestone 1)
  - EDC17C46/CP44, MED9.1, ME7.x — planned (Milestone 2)
  - MED17.1 not listed at all, even as a future milestone, as of this check.
- NOT usable for our ECU yet. Revisit if MED17.1 support is ever added.
- Mentions a companion "TriCoreTool" (ROM editor, produces .bin) in its toolchain diagram —
  not yet investigated.

### vag-ecu-re (oscarmcnulty) — reverse-engineering toolkit, VAG TriCore ECUs
MED17 pack covers an Audi Q5 2.0 TFSI (MED17.1.1 family, close sibling). Built on Ghidra.
Not yet investigated in depth.

### ghidra-tc1797 (christianobora) — https://github.com/christianobora/ghidra-tc1797
Ghidra processor definition files for the TC1797 chip, built while reverse-engineering an
Audi MED17.1.1. Real tooling for doing our own disassembly if it comes to that.

### medc17-checksum-tool (ConnorHowell)
Free checksum analyzer/corrector for Bosch MED17/EDC17 (CRC32/ADD32/ADD16). Notes a
"variant dataset block with a table of parameter addresses" structure — may be useful
reference for understanding MED17's internal data layout.

### Next step
Pick one to actually try. ECU-Studio-AI is the most directly relevant (map-finding without
a definition, works on an already-read bin, no ECU-specific support gap like VAGFlasher has)
— likely starting point once we have a real dump from the KTAG.
