# UDS v3 contract: CONTRACT 2

**Status: CONTRACT 2, V3-CHIP, 2026-10-18 about 14:55 Riga (CONTRACT 1 was frozen at 14:05).** V3-CHIP owns this file; other sessions
read it and ask on the [tracker](https://github.com/ai-wrangler/tt-uds-v3/issues/1). `docs/v3/params.json` is
its machine-readable twin. The bit-exact definition of every formula below is `model/uds3_model.py`.

## Changes

- **CONTRACT 2** (area: the chip did not fit with two amplitudes per voice):
  - `mode` no longer gives the tone and the noise separate amplitudes. Both follow the main envelope; modes 1
    to 3 move the **noise share** (the mix) with the aux envelope instead. See the mode row below. The HIT
    layout, the ids, the clock and the protocol are unchanged.
  - The pitch bend uses the aux value after this frame's step (an internal detail of the model; it does not
    change any field).
- **CONTRACT 1** (replaces DRAFT 0):
  - Clock 8 MHz (was 12), frame 128 clocks (2 voices x 64), still 62.5 kHz.
  - Every byte of a HIT is followed by a BUSY wait (the chip writes the patch into the voice byte by byte; this
    saved a 32-bit buffer).
  - New HIT layout. Kept: pitch, decay, level, bend, bend time, mix, wave, noise color, clap. Added: envelope
    mode (split decay), click (start phase). Snap became the 1-bit click. Bend is 2 bits (0 to 3 octaves),
    bend time 3 bits.
- If area forces a cut later, the cut field's bits become reserved (ignored) in the next contract. The other fields
  do not move.

## Clock and frame

- **8 MHz.** One frame = 128 clocks = window 0 (voice 0) + window 1 (voice 1), 64 clocks each: 62.5 kHz.
- Pitches and times are counted in frames, so they scale with the clock (at 12 MHz everything is 1.5 x
  higher and faster).
- **2 voices.** A 3rd voice does not fit next to the per-HIT patch (see `docs/v3/REPORT.md`).

## Pins (as v1; top module `tt_um_ai_wrangler_uds3`)

| Pin | Signal |
| --- | --- |
| uio[0] | CS_N (in) |
| uio[1] | MOSI (in) |
| uio[2] | MISO (out) |
| uio[3] | SCK (in) |
| uio[4] | FRAME (out): high during window 0 |
| uio[5] | BUSY (out) |
| uio[6], uio[7] | AUDIO (out), same as uo[7] |
| uo[6:0] | 7-segment digit of the channel of the last HIT |
| uo[7] | AUDIO: second-order 1-bit sigma-delta |

ui_in is unused.

## SPI

Mode 0, MSB first, SCK at most clk / 6, CS low for the whole message.

| Message | Bytes |
| --- | --- |
| HIT | `0x18` + ch, then P0, P1, P2, P3 |
| READ | `0x30` + reg, then a dummy byte; the answer comes on MISO during the dummy byte. Reg 0 = ID `0xD5`, reg 1 = VERSION `0x32` (3 = v3, 2 voices), others 0. |
| STOP | `0x40`: every voice goes silent in the next frame |

**BUSY handshake.** After **every byte of a HIT** (the command byte and P0 to P3), wait at least 4 clocks, then
wait until BUSY is low before you clock the next byte or start the next message. BUSY rises within 3 clocks of
the byte's 8th SCK rising edge and falls at a window end:

- after the command byte, at the end of the frame (the target voice is chosen then);
- after a patch byte, at the end of the target voice's next window (the byte is written then).

A HIT therefore takes about 10 windows (80 to 110 µs at 8 MHz). The voice goes silent when P0 is written and
starts with the new patch in the frame after P3 is written. READ and STOP need no BUSY wait.

**Voice choice** (at the frame end after the command byte): the voice already playing the same channel
(channels 6 and 7 count as one: hi-hat choke), else a free voice (voice 0 first), else the quieter one by
env[7:5] (voice 0 on ties).

## HIT patch: 32 bits

| Byte | Bits | id | Meaning |
| --- | --- | --- | --- |
| P0 | 7:0 | pitch | Base pitch, 32 steps per octave: phase increment (32 + p[4:0]) << p[7:5] per frame on a 16-bit phase. 30.5 Hz at 0, 61 Hz at 32, 122 Hz at 64, 244 Hz at 96, 488 Hz at 128, 7.69 kHz at 255. |
| P1 | 7:4 | decay | Main envelope: one step every 2^decay frames (13 to 15 act as 13). A step is env -= env >> 3 (env -= 1 below 8). -30 dB after 30 steps: 0.5 ms at 0, 4 ms at 3, 32 ms at 6, 0.25 s at 9, 4 s at 13. |
| P1 | 3:2 | wave | 0 triangle; 1 driven (2 x triangle, clipped); 2 square; 3 metal (the square XOR fixed squares at fs/2 and fs/8, inharmonic). |
| P1 | 1:0 | color | Noise color, from one shared 17-bit LFSR: 0 dark (average of 4 samples), 1 white, 2 bright (first difference), 3 metallic buzz (fixed squares at fs/4, fs/16, fs/32 XORed). |
| P2 | 7:6 | bend | Pitch envelope depth: effective pitch = min(255, pitch + aux x bend / 8), so at the attack (aux = 255) 0, 31, 63 or 95 steps higher (0, 1, 2, 3 octaves), falling with the aux envelope. |
| P2 | 5 | res | Reserved: send 0. |
| P2 | 4:2 | bendtime | Aux envelope speed. Modes 0 to 2: one step (aux -= aux >> 3, -1 below 8) every 2^(bendtime+3) frames; aux falls to 1/4 in 1.4 ms at 0, 5.6 ms at 2, 11 ms at 3, 23 ms at 4, 45 ms at 5, 90 ms at 6, 180 ms at 7. Mode 3: aux -= 1 every 2^bendtime frames. |
| P2 | 1:0 | mode | Envelope mode, with a3 = aux >> 5 (7 at the attack, 0 once aux < 32). 0: the noise share is mix. 1 "short tone": share = max(mix, 7 - a3), so the tone part hands over to the noise as aux falls (snare body + noise tail). 2 "short noise": share = min(mix, a3), so the noise part fades out with aux (kick click). 3 "clap": the tone is muted; while aux >= 64 the share is (aux >> 3) & 7, a falling ramp that restarts every 64 aux steps (3 bursts 64 x 2^bendtime frames apart), then the share is mix (the tail). |
| P3 | 7:5 | mix | Noise share: on share/8 of the output clocks the voice plays the noise, on the rest the tone; share 7 = noise only. The share is mix, moved by the mode. |
| P3 | 4:1 | level | Start level: env starts at 17 x level (0 = silent). aux always starts at 255. |
| P3 | 0 | click | Start phase: 0 = 0x4000 (the triangle starts at zero, rising: soft); 1 = 0x8000 (it starts at its peak: a click). |

The aux envelope is the voice's second envelope: it starts at 255 on every HIT and drives the bend, the noise
share in modes 1 to 3 and the clap bursts. Loudness always follows the main envelope.

## Output (exact form in the model)

- Per window the voice outputs an 8-bit tone sample (triangle from phase[15:7], or the wave) and an 8-bit
  noise sample. On each clock t of its window the voice plays the noise if t's pattern ({t0,t1,t2} < share,
  or share = 7) says so, else the tone. Loudness is made in time: the DAC gets the source on clocks
  t < env >> 3, source >> 3 on the next env & 7 clocks, and 0 on the rest.
- DAC: second-order 1-bit sigma-delta, as on `sd2` at 1/16 scale (feedback +-256 for samples up to +-128).
  When no voice sounds, the loop restarts and idles at the clean 0110 pattern (64 ones per frame).
- Filter: the Audio Pmod, or RC 1 kΩ + 10 nF.

## Kits

`kits/<id>.json` with `"contract": 1` and `patch` objects using the ids above (missing ids = 0). `res` may be
omitted.
