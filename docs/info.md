<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

UDS v3 is an 8-channel drum synthesizer for current electronic music: punchy kicks with a fast pitch drop,
snares that snap, real claps, crisp and metallic hats, toms and zaps. It is the third version of UDS, a
digital homage to the Formanta UDS. There are no samples and no patch memory: **every HIT carries the full
sound of its channel** (a 32-bit patch), so the controller keeps one patch per channel and knobs can change
any channel's sound live. Two voices sound at once.

A new HIT takes the voice of the same channel if it still sounds (channels 6 and 7 count as one: hi-hat
choke), else a free voice, else the quieter one.

### One voice

- **Oscillator:** a triangle with an exponential pitch (8 bits, 32 steps per octave, 30.5 Hz to 7.7 kHz at
  8 MHz). The wave can also be a driven (clipped) triangle, a square, or "metal": the square XORed with fixed
  squares, for bells and cowbells.
- **Noise:** one shared 15-bit LFSR in four colors: dark, white, bright (first difference) and a metallic
  buzz.
- **Main envelope:** exponential decay from 17 x level, -1/8 per step, one step every 2^decay frames (0.5 ms
  to 4 s to -30 dB). Loudness always follows it.
- **Aux envelope:** a second exponential envelope that starts at 255 on every HIT, with its own speed
  (bendtime). It drives:
  - the **pitch bend:** the pitch starts 0, 1, 2 or 3 octaves higher and falls back with it (kicks, toms,
    zaps);
  - the **envelope mode:** the share of noise in the sound moves with it. "Short tone" hands a tone body over
    to a noise tail (snares), "short noise" makes a noise click that fades on a long tone (kicks), "clap"
    plays three noise bursts and then the tail.
- **Click:** the triangle can start at its peak instead of at zero, for a hard attack.

### How it fits in one tile

- **The ring.** All voice state sits in one 128-bit shift register: two 64-bit voice words that move one bit
  per clock. Each voice passes the end of the ring once per 128-clock frame (62.5 kHz at 8 MHz). Its
  envelopes and its 16-bit phase are updated bit by bit on the way.
- **Patch written byte by byte.** A HIT is written into its voice one byte at a time, as the voice word
  passes. There is no 32-bit HIT buffer.
- **Loudness made in time.** There is no multiplier. During its 64-clock window a voice gives the DAC its
  8-bit sample on env/8 clocks and 1/8 of it on env mod 8 clocks. On each clock a fixed pattern picks the
  tone or the noise, by the noise share.

### Audio DAC

- **Second-order 1-bit sigma-delta at the full clock rate**, as on UDS v2. The integrators are 11 and
  13 bits, the feedback is +-256, and the samples are at most +-128 (half scale).
- **Silence.** When no voice sounds, the loop restarts and plays a clean 0110 pattern (64 ones per frame).
- **Filter** the audio pin with the Audio Pmod or an RC low-pass of 1 kOhm and 10 nF.

The engine is specified by a bit-exact Python model (`model/uds3_model.py`). The tests check the chip against
it window by window, on the RTL and on the gate-level netlist. `model/uds3_render.py` renders patches and
hits to a WAV file through the same model.

## SPI protocol

SPI mode 0, MSB first, SCK at most clk/6, CS low for the whole message. The clock is 8 MHz (other clocks
work; pitches and times scale with it).

| Message | Bytes |
| --- | --- |
| HIT | `0x18 \| ch`, then P0, P1, P2, P3 |
| READ | `0x30 \| reg`, then a dummy byte; the answer comes on MISO during the dummy byte. reg 0: ID `0xD5`; reg 1: VERSION `0x32` |
| STOP | `0x40`: every voice goes silent |

**BUSY:** after every byte of a HIT, wait at least 4 clocks, then until BUSY (uio[5]) is low, before the next
byte or message. A HIT takes about 80 to 110 µs at 8 MHz. READ and STOP need no wait.

### The patch

| Byte | Bits | Field | Meaning |
| --- | --- | --- | --- |
| P0 | 7:0 | pitch | f = 62.5 kHz x (32 + p mod 32) x 2^(p div 32) / 65536 at 8 MHz: 30.5 Hz at 0, 61 Hz at 32, 122 Hz at 64, 244 Hz at 96, 488 Hz at 128, 7.69 kHz at 255 |
| P1 | 7:4 | decay | main envelope step every 2^decay frames (13-15 = 13). To -30 dB: 0.5 ms at 0, 4 ms at 3, 32 ms at 6, 0.25 s at 9, 4 s at 13 |
| P1 | 3:2 | wave | 0 triangle, 1 driven triangle, 2 square, 3 metal |
| P1 | 1:0 | color | noise: 0 dark, 1 white, 2 bright, 3 metallic |
| P2 | 7:6 | bend | pitch starts 0, 1, 2 or 3 octaves higher (offset = aux x bend / 8 steps) |
| P2 | 5 | res | reserved, send 0 |
| P2 | 4:2 | bendtime | aux envelope step every 2^(bendtime+3) frames: aux falls to 1/4 in 1.4 ms at 0, 5.6 ms at 2, 11 ms at 3, 23 ms at 4, 45 ms at 5, 90 ms at 6, 180 ms at 7. In clap mode: aux -1 every 2^bendtime frames, bursts 64 x 2^bendtime frames apart (8 ms at 3) |
| P2 | 1:0 | mode | 0 normal; 1 short tone (tone body hands over to noise); 2 short noise (noise click fades out); 3 clap (tone muted, 3 noise bursts, then the tail) |
| P3 | 7:5 | mix | noise share in eighths (7 = noise only) |
| P3 | 4:1 | level | start level: env = 17 x level |
| P3 | 0 | click | 1: the triangle starts at its peak (hard attack) |

`docs/v3/CONTRACT.md` gives the exact rules and `docs/v3/params.json` the same fields in machine-readable
form.

### Starting sounds

| Sound | pitch | decay | wave | color | bend | bendtime | mode | mix | level | click |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Kick | 12 | 7 | 1 driven | 0 | 3 | 3 | 2 short noise | 2 | 15 | 1 |
| Snare | 110 | 6 | 0 | 1 white | 1 | 3 | 1 short tone | 3 | 12 | 0 |
| Clap | 0 | 7 | 0 | 1 white | 0 | 3 | 3 clap | 7 | 13 | 0 |
| Closed hat | 0 | 3 | 0 | 2 bright | 0 | 0 | 0 | 7 | 9 | 0 |
| Open hat | 0 | 7 | 0 | 3 metallic | 0 | 0 | 0 | 7 | 9 | 0 |
| Tom | 70 | 7 | 0 | 0 | 1 | 4 | 0 | 0 | 13 | 0 |
| Cowbell | 150 | 6 | 3 metal | 0 | 0 | 0 | 0 | 0 | 11 | 0 |
| Zap | 60 | 5 | 2 square | 0 | 3 | 5 | 0 | 0 | 12 | 0 |

The kits in `kits/` (made by V3-SOUND) give complete sets of eight sounds.

## How to test

1. Clock the chip at 8 MHz from the demoboard (the RP2350 can set it) and reset it.
2. Connect an Audio Pmod (or a 1 kOhm / 10 nF RC filter and an amplifier) to uo[7] or uio[6]/uio[7].
3. Over SPI, READ register 0 (expect 0xD5) and register 1 (expect 0x32).
4. Send a kick: `18 0C 74 CE 5F` for channel 0. Wait for BUSY low after each byte. The 7-segment display shows
   0.
5. Play the starting sounds, or load a kit from `kits/` in the browser twin (https://ai-wrangler.github.io/uds-virtual/),
   which drives the same protocol.

## External hardware

- Audio Pmod or RC filter (1 kOhm, 10 nF) and an amplifier.
- 7-segment display on uo[6:0] (the demoboard's), showing the channel of the last HIT.
- An SPI controller: the RP2350 on the demoboard, or any microcontroller.
