# UDS v3 voice features, ranked by musical impact (V3-SOUND)

For deep house / techno / electro / electronica drums inspired by GusGus, Simian Mobile Disco, Trentemøller and
Röyksopp. Ranges come from the numpy prototype `model/sound_proto.py` (62.5 kHz frame, integer state, no
per-sample multiplier) and from what the target sounds need. "Per-voice bits" is the extra state in the voice
word; patch bits ride in the HIT and are stored only while the voice plays.

## What the research says (short)

- **GusGus:** analog/modular drum sounds made on a Doepfer system and resampled; kicks are hit hard with a
  Distressor into "dancefloor hammers"; Biggi Veira's "never-ending quest for the perfect kick"
  ([MusicTech](https://musictech.com/features/studios/show-off-your-studio-gusgus-and-the-monophony-monster-wall/)).
  → punchy, driven kick; synthetic (not sampled-acoustic) percussion.
- **Simian Mobile Disco:** beats built on modular (Analogue Systems, Doepfer) to avoid stock drum-machine
  palettes; the kick is three layers: a tuned sub from a filter near self-oscillation, a "click-y kick" from
  white noise, and a non-tuned low layer from cross-modulated sines or low-passed noise
  ([Patrick Sisson / SMD](https://patricksisson.com/all-mod-cons-simian-mobile-disco%e2%80%99s-modular-synths-make-for-striking-techno-pop/));
  live percussion: congas, tambourine, roomy woodblocks
  ([FACT Signal Path](https://factmag.com/2018/06/09/simian-mobile-disco-signal-path)).
  → tuned kick + noise click; woodblock/conga-like tuned percussion; atonal noise (Serge).
- **Trentemøller:** percussion programmed from ~200 "very high-end and trebly digital clicks" sampled from a
  broken CD, plus live kit, brushes and ride
  ([MusicRadar, The Last Resort](https://musicradar.com/news/classic-album-trentmoller-on-the-last-resort));
  tape (Revox B-77) to glue drums ([MusicRadar, career in gear](https://www.musicradar.com/news/trentemoller-career-in-gear)).
  → tiny bright clicks and ticks, short metallic/glitch percussion, dark long tails.
- **Röyksopp:** Akai S1000 "distinctive crunch", overdriven mixer preamps, Korg DDD-1; they avoided stock 909
  sounds on *Melody A.M.* ([gearnews](https://www.gearnews.com/nordic-electronic-pioneers-how-to-sound-like-royksopp),
  [Stereogum](https://stereogum.com/2159383/royksopp-melody-a-m-turns-20/reviews/the-anniversary)).
  → slightly crunchy, warm, lo-fi drums; claps and snappy snares over house kicks.

## Ranking

| # | Feature | Range it needs | Cost (estimate) | Lost without it |
| --- | --- | --- | --- | --- |
| 1 | **Fast exponential pitch envelope** on the oscillator (aux env, added to the pitch in 32-steps/oct units) | depth 0 to 48 semitones (kick 24 to 36, toms 7 to 18, zaps 36 to 48); time to fall to 1/4 of the offset ~5 to 120 ms (kick 10 to 40, zap 40 to 120) | 8 b aux env per voice + 5 patch bits (bend 3, bendtime 2); offset = aux × const as a 2 to 3 term shift-add | Every modern kick, tom and zap. Without it a kick is a boomy sine tone; this is the single most important feature. |
| 2 | **Split decay: tone and noise fade differently** | cheap form: 1 to 2 patch bits, tone (or noise) amplitude = min(env, aux), so one part follows the fast aux env (5 to 120 ms) and the other the main env (30 ms to 1.5 s). Full form: a second 8-bit noise env with its own 4-bit decay | cheap: a comparator + mux, 0 per-voice bits (reuses #1's aux). full: +8 b/voice + 4 patch bits | Snares (short tonal body 30 to 80 ms + 150 to 300 ms noise tail), kick + noise click, rim shots. Without it a snare is either a ringing tone or plain hiss. |
| 3 | **Main amp decay range and level** (as v1, exponential) | -30 dB in ~0.5 ms (ticks) to ~2 s (ride, dub tails); 4-bit level | already there | Ticks/clicks (Trentemøller) need very short; claps/rides need long. Keep both ends. |
| 4 | **Clap bursts** | 3 to 4 noise bursts 8 to 12 ms apart, each falling ~10 dB in 3 to 5 ms, then the main-env tail (80 to 400 ms) | 1 patch bit; the timer reuses the aux env counter / age bits; no new state if the aux env is free while clap is on | Real house claps, central to all four styles. Without it the "clap" is only a noise snare. |
| 5 | **Noise colours from ONE global LFSR** | dark (~1 to 3 kHz 1-pole LP), white, bright (first difference, HP +6 dB/oct), metallic | global only: ~9 b LP state + 8 b previous sample, shared; 2 patch bits | Hats need bright; shakers/brushes and dark tails need dark. Without colours all hats sound like the same grey hiss. |
| 6 | **Metal wave**: tone square XOR fixed inharmonic squares | tone 300 Hz to 8 kHz XOR fixed squares near fs/6, fs/10, fs/14 | global counters (a few bits), 2 patch-bit wave select shared with #7/#8 | Cowbells, bells, rides, metallic glitch perc. Without it no cymbal/cowbell family. |
| 7 | **Driven (clipped) triangle** | gain ~2.5x then clamp | combinational only | Fatter, harder kicks (GusGus "hammer", Röyksopp crunch) and saturated toms/bass. Kicks get thinner without it, but it is cheap. |
| 8 | **Click / snap transient** | 0.1 to 1.5 ms, 3 bits strength | gate from aux/age bits, no new state | Kick definition on small speakers; Trentemøller-style ticks. Partly fakeable with bend 7 + bendtime 0 + very short decay, so lower. |
| 9 | **Square wave** | — | 2-bit wave select | Electro bleeps, zaps, 808-ish cowbell layers. Triangle + drive covers most of it. |

Not worth the area: resonant filters, FM, LFOs, per-voice noise generators (share one LFSR), on-chip patch memory.

## If area forces cuts

Cut from the bottom: 9, then 8, then the full form of 2 (keep the cheap min(env, aux) split), then 7.
Never cut 1, 3 or 4. With 2 voices, voice stealing is the real limit for these styles (kick + hat + clap
overlap all the time): **a 3rd voice is worth more than features 6 to 9 together.**
