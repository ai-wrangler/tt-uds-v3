# V3-CHIP architecture notes (working file)

Started 13:14 Riga. These are working notes; `CONTRACT.md` is the source of truth once CONTRACT 1 lands.

## Area calibration

Local estimate: Yosys 0.33 `synth -flatten` + `abc` to `sky130_fd_sc_hd__tt_025C_1v80.lib` (open_pdks 0fe599b),
`stat -liberty`.

| Design | Yosys estimate | TT flow std-cell area | Ratio | FFs |
| --- | --- | --- | --- | --- |
| v1 (tt-uds-1x1 main) | 8 589 µm² | 12 842 µm² | 1.495 | 235 |
| v2 (sd2, this repo's start) | 9 869 µm² | 14 805 µm² | 1.500 | 254 |

So flow ≈ 1.50 × Yosys. The core holds ~16 490 µm²; 88 % utilization = 14 510 µm² flow = **~9 670 µm² Yosys**.
v2 is already 9 869, so v3 has to save area before it can add anything.

## Direction (draft)

- 2 voices, 64-bit voice word, 128 clocks per frame. At 8 MHz that is 62.5 kHz, the v1 frame rate, so v1's
  pitch and decay tables carry over. (A 192-clock frame with 2 voices would waste 32 ring bits per voice.)
- 3rd voice: +64 ring FFs ≈ +1 300 µm² Yosys ≈ +2 000 µm² flow ≈ +12 % utilization. Features 6 to 9 are mostly
  combinational and cost a few hundred µm². The 3rd voice does not fit next to the per-channel patch.
- Cheaper SPI buffer: commit the HIT byte by byte into the target voice's word (8-bit receive register + 8-bit
  hold register instead of a 32-bit payload register). Costs a slower SCK limit.
- Patch fields that only matter at the start (level, start phase) are not stored.
- One 8-bit aux envelope per voice drives the pitch bend, the split decay and the clap bursts.
