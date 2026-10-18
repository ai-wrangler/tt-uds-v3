# UDS v3: chip report (V3-CHIP)

Written by V3-CHIP on 2026-10-18. Every number here comes from a run that was done: the Tiny Tapeout flow in this
repo's GitHub Actions (`final/metrics.json` of the GDS_logs artifact), or local Yosys, Icarus and cocotb.

## 1. What was built

- **Top module:** `tt_um_ai_wrangler_uds3` (`src/project.v`, `src/uds3_spi.v`, `src/uds3_core.v`). It uses the
  v1 pins.
- **Clock and voices:** 8 MHz, 2 voices, 128-clock frame (62.5 kHz).
- **Patch per HIT:** every HIT carries a full 32-bit patch (CONTRACT 2, `docs/v3/CONTRACT.md`), so all 8
  channels are fully editable from the controller.
- **Messages and pins:** READ ID 0xD5, READ VERSION 0x32, STOP, BUSY, FRAME, 7-segment digit, and the
  second-order sigma-delta DAC.
- **Spec of record:** `model/uds3_model.py` (bit-exact).
  - `model/uds3_render.py` renders patches and hits to a WAV file through the DAC model and the RC filter.
  - `model/ab_render.py` makes the v2/v3 A/B renders.
- **Tests:** `test/` holds cocotb tests that compare the chip with the model every 64-clock window: the 1s on the
  audio pin, BUSY, FRAME and the digit. They run on the RTL and on the gate-level netlist.
- **Fixtures for the browser twin:** `test/fixtures/` (pin schedule and expected outputs), made by
  `test/make_fixtures.py`.

## 2. Architecture

| | v1 (tt-uds-1x1 main) | v2 (sd2) | v3 |
| --- | --- | --- | --- |
| Clock / frame | 6 MHz / 96 | 6 MHz / 96 | 8 MHz / 128 |
| Voices | 2 | 2 | 2 |
| Voice word | 48 bits | 48 bits | 64 bits |
| HIT patch | 24 bits | 24 bits | 32 bits, written byte by byte |
| Pitch envelope | tied to the main env | tied to the main env | own aux envelope, 0 to 3 octaves, 1.4 to 180 ms |
| Tone / noise | triangle; LP noise or metal by channel | same | 4 waves, 4 noise colors, any channel |
| Envelope modes | none | none | normal, short tone, short noise, clap (3 bursts) |
| DAC | 1st order | 2nd order, 15/17-bit integrators | 2nd order, 11/12-bit integrators (samples 8-bit) |

How the area was found:

1. **The ring.** Voice state is a 128-bit shift ring, as in v1. A 192-clock frame (DRAFT 0) would have
   wasted 32 ring bits per voice, so the frame is 2 x 64 clocks.
2. **No HIT buffer.** The HIT is not buffered: each byte is written into the target voice in its next window,
   and the host waits for BUSY after every byte. This needs an 8-bit receive register instead of a 32-bit
   buffer.
3. **Bits that are not stored.** Level and click only act at the start of a hit, so they are not stored.
4. **One shared sample register.** The tone sample register is reloaded on clock 47 with the effective
   pitch, so one 8-bit register serves both.
5. **One amplitude per voice.** CONTRACT 1 had separate amplitudes for tone and noise (min(env, aux)), and it did
   not fit (section 3). In CONTRACT 2 the envelope modes move the noise share with the aux envelope instead.
6. **Smaller arithmetic.** The samples are 8 bits, so the DAC runs at 1/16 of the sd2 scale. The DAC has no
   clamps: the worst simulated |v1| is 766 of 1023 and |v2| is 1270 of 2047, measured over random and
   resonant slot patterns at full level.
7. **Cheap metal and noise.** The metal wave and the metallic noise use frame-counter squares instead of
   v1's three extra counters.

## 3. Area and timing

Real flow, `final/metrics.json` (std-cell area includes the tap, clock and timing-repair cells; the core is
16 493 µm²):

| Run | Std-cell area | Utilization | Hold buffers | Setup WS | Hold WS | Result |
| --- | --- | --- | --- | --- | --- | --- |
| v1 (given) | 12 842 | 77.9 % | | +8.95 ns | +0.022 ns | pass |
| v2 sd2 (given) | 14 805 | 89.8 % | | +5.87 ns | +0.029 ns | pass |
| area-x2: CONTRACT 1, two amplitudes, 9-bit samples | ~16 100 at CTS | 92 % at global placement | 146 | | | detailed placement failed |
| area-x3: 8-bit samples, SYNTH_STRATEGY AREA 0 / 1 / 2 | 14 264 / 14 320 / 14 329 at CTS | 90.9 / 90.5 / 90.9 % GPL | 144 to 147 | | | detailed placement failed |
| area-x3, AREA 3 | | 102.7 % GPL | | | | global placement failed |
| area-x3-inv: an inverter between ring stages | 14 871 at CTS | 93.1 % GPL | 141 | | | failed (the inverters did not save hold buffers) |
| area-x5: CONTRACT 2 RTL | 14 708 | 89.2 % | 128 | +6.49 ns | +0.026 ns | pass |
| main 43875dc (x5 + 12-bit v2 + flags from captured env) | 14 521 | 88.0 % | 131 | +6.70 ns | +0.029 ns | pass |
| **main baed8b7 (+ 15-bit LFSR): final** | **14 454** | **87.6 %** | 130 | **+5.73 ns** (max_ss) | **+0.026 ns** (min_ff) | **pass**: gds, precheck, gl_test, viewer |

- Timing is checked at 20 ns, so there is a large setup margin for 8 MHz (125 ns).
- Hold is positive at all 9 corners.
- The flow reports max-slew warnings at the ss corners (about 140 pins). It completes, and precheck passes.
- **3rd voice:** +64 ring bits, plus the choice logic and their hold buffers, is about +2 000 µm² (+12 %).
  - The 2-voice design with the per-HIT patch is already at the limit, so a 3rd voice cannot fit next to it.
  - V3-SOUND's stealing study (2 voices cut about 20 % of hits in these styles, 3 voices about 5 %) is the main
    trade-off left: see section 6.

## 4. Tests

- **RTL (Icarus 12, cocotb 2.1, local and in the `test` workflow):**
  - test_id: ID 0xD5, VERSION 0x32.
  - test_kit: 4166 windows. Every voice feature, voice stealing, the hi-hat choke, and STOP.
  - test_random: 2050 windows. 40 random patches, which covers every field value.
  - All of them are bit-exact on every window.
- **Gate level (gl_test job):** the same tests on the netlist from the flow, bit-exact. They passed on d768a89
  (short kit test, 1606 windows), and on 43875dc and baed8b7 (full test_kit and test_random).
- **What the window comparison checks:** the number of 1s on the audio pin in each window, BUSY at each
  window start, FRAME, and the 7-segment digit.

## 5. Audio

- `docs/v3/audio/ab_default.mp3` and `ab_reykjavik.mp3`: the same MIDI pattern twice in each file, first on
  v2 (its 8 presets, 6 MHz), then on v3 (the kit), at the same gain. Both go through their own DAC model,
  RC 1 kΩ / 10 nF, then 48 kHz.
- `docs/v3/audio/<kit>.mp3`: V3-SOUND's kit renders through `model/uds3_render.py`.

## 6. What was cut, and why

| Cut | Why |
| --- | --- |
| 3rd voice | Did not fit: about +12 % (section 3). |
| Separate tone and noise amplitudes (CONTRACT 1 modes, min(env, aux)) | Over budget by about 4 %. Replaced by aux-moved noise share (CONTRACT 2). Snare and kick-click shapes are kept, but the short part steps in 1/8 shares instead of a smooth fade. |
| Snap strength (3 bits) | Replaced by a 1-bit click (start phase at the peak). |
| Bend depth 3 bits → 2 bits (0 to 3 octaves) | Saves an adder. |
| Inharmonic fs/6, fs/10, fs/14 counters | The metal wave and metallic noise use frame-counter squares. |
| LFSR 17 → 15 bits | The noise repeats every 0.52 s instead of 2.1 s. This is about the margin under 88 %. |

## 7. Status and open points

Final RTL: `main` baed8b7. All of gds, precheck, gl_test, test, docs and viewer pass. 87.6 % utilization.
Setup and hold slack are positive at all 9 corners.

- **Not verified on silicon or on an FPGA.**
- The twin (V3-WEB) runs the Verilog itself. Its truth test should replay `test/fixtures/*.json`.
- **For Juris:**
  - whether v3 goes on TTSKY26d as its own tile or instead of v1;
  - whether the 3rd voice matters more than the per-HIT patch. It cannot have both in 1x1; a 1x2 tile would
    fit both;
  - whether to accept the 88 % utilization, or to drop the drive wave (about -1 %) for more margin.
