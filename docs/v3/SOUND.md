# UDS v3 sound (V3-SOUND)

Status: **kits written against CONTRACT 2 and rendered through V3-CHIP's bit-exact model**
(`model/uds3_model.py` + `model/uds3_render.py` at d768a89, which V3-CHIP reports bit-exact against the RTL in
its cocotb tests). The early numpy prototype (`model/sound_proto.py`, DRAFT 0) was used only for the ranking.

## 1. Research: what defines the four styles

Only "inspired by". No samples, no transcribed parts: every sound here is synthesized and every pattern is
original.

| Artist | Kicks | Snares / claps | Hats / cymbals | Percussion / FX | Sources |
| --- | --- | --- | --- | --- | --- |
| **GusGus** | Analog/modular kicks pushed hard through a compressor into "dancefloor hammers"; a "never-ending quest for the perfect kick" | House claps and snares over a steady four-on-the-floor | Off-beat open hats, shakers | Percussion made on a Doepfer modular (LFOs switched to VCOs for extra oscillators), resampled into their own palette | [MusicTech studio feature](https://musictech.com/features/studios/show-off-your-studio-gusgus-and-the-monophony-monster-wall/) |
| **Simian Mobile Disco** | Three layers: tuned sub from a filter near self-oscillation, a "click-y" white-noise kick, a non-tuned low layer from cross-modulated sines or filtered noise | Snappy, electro-leaning | Metallic, sequenced 16ths | Modular (Analogue Systems, Doepfer, Serge for atonal noise); live congas, tambourine, roomy woodblocks; free-time nudged swing | [Patrick Sisson](https://patricksisson.com/all-mod-cons-simian-mobile-disco%e2%80%99s-modular-synths-make-for-striking-techno-pop/), [FACT Signal Path](https://factmag.com/2018/06/09/simian-mobile-disco-signal-path) |
| **Trentemøller** | Deep, soft, long | Brushes, live kit, gentle noise snares | Ride, very thin bright hats | ~200 "very high-end and trebly digital clicks" from a broken CD used as percussion; tape glue | [MusicRadar: The Last Resort](https://musicradar.com/news/classic-album-trentmoller-on-the-last-resort), [MusicRadar: career in gear](https://www.musicradar.com/news/trentemoller-career-in-gear) |
| **Röyksopp** | Round, warm, slightly crunchy | Fat snares and claps; they skipped stock 909 sounds | Swung closed/open hats | Akai S1000 "crunch", overdriven mixer preamps, Korg DDD-1; "cartoonish", "buoyant, busy" beats | [gearnews](https://www.gearnews.com/nordic-electronic-pioneers-how-to-sound-like-royksopp), [Stereogum](https://stereogum.com/2159383/royksopp-melody-a-m-turns-20/reviews/the-anniversary) |

What the chip has to do, then: a fast pitch-swept kick with drive and a click; claps with real bursts; snares
whose tone and noise fade differently; bright, short hats from noise; metallic and glitchy short percussion;
tuned wood/skin hits (woodblock, conga, bongo); and zaps.

## 2. Feature ranking

See [FEATURE_RANKING.md](FEATURE_RANKING.md) (posted on the tracker at 13:00 Riga).

## 3. Kits

| Kit | Inspired by | Tempo | Intent | Pattern | Render |
| --- | --- | --- | --- | --- | --- |
| [Default](../../kits/default.json) | — | 124 | GM all-rounder: kick, snare, 3 toms, ride, closed/open hat | Four-on-the-floor, backbeat snare, off-beat hats, ride on 1 and 3, tom fill in bar 4 | [default.mp3](audio/default.mp3) |
| [Reykjavík](../../kits/reykjavik.json) | GusGus | 122 | Deep driven house: hammer kick, burst clap, shaker, bongos, rim, airy open hat | Swung (12 %) house: off-beat open hat, 16th shaker, bongo answers, rim pushes | [reykjavik.mp3](audio/reykjavik.mp3) |
| [Shoreditch](../../kits/shoreditch.json) | Simian Mobile Disco | 126 | Modular techno/electro: sub kick with noise click, electro snare, woodblock, conga, zap, cowbell, metal hats | Straight 16th metal hats, woodblock/conga syncopation, off-beat cowbell, zaps at phrase ends | [shoreditch.mp3](audio/shoreditch.mp3) |
| [Copenhagen Night](../../kits/copenhagen.json) | Trentemøller | 120 | Dark minimal: deep long kick, trebly ticks and glitch clicks, brush snare, metal knock, dark ride | Half-time kick and snare, busy tick grid, sparse glitch clicks and knocks, one ride per two bars | [copenhagen.mp3](audio/copenhagen.mp3) |
| [Tromsø](../../kits/tromso.json) | Röyksopp | 116 | Warm crunchy pop-house: round driven kick, snare-clap in one voice, clap, jingle, soft toms | Lightly swung (8 %) pop-house kick, snare-clap backbeat, open hat lifts, jingle pickups, tom fill | [tromso.mp3](audio/tromso.mp3) |

Demo patterns (original, 4 bars, GM drums on channel 10, tempo set): `kits/patterns/<id>.mid`.
Renders: `docs/v3/audio/<id>.mp3`: the model's bitstream, counted per frame (62.5 kHz), through the board's RC filter (1 kΩ + 10 nF), peak-normalized.

## 4. How each sound is made (CONTRACT 2 fields)

Cheat sheet: pitch 30.5 Hz × 2^(p/32); decay d reaches -30 dB after 30 × 2^d frames (8: 123 ms, 9: 246 ms);
bend 0 to 3 octaves; bendtime 0 to 7 = aux to 1/4 in 1.4 to 180 ms. Loudness always follows the main envelope;
`mode` moves the noise share with the aux envelope: 1 short tone (the share grows from `mix` to all noise),
2 short noise (the share falls from `mix` to 0), 3 clap (tone muted, 3 noise bursts, then `mix`).

- **Kicks** (all kits): pitch 16 to 24 (40 to 50 Hz), `bend` 2 to 3 (+24 to +36 semitones), `bendtime` 3 to 5
  (11 to 45 ms). Reykjavík and Tromsø use the driven triangle (harder, "hammer"); Shoreditch and Default add a
  short noise click with `mode` 2 + `mix` 1 to 2, a noise share that fades out in ~15 ms (SMD-style click layer on a tuned sub); `click` starts the
  triangle at its peak. Copenhagen's deep kick is a plain triangle with a slow bend (45 ms) and no click.
- **Snares:** a triangle/square/driven body at 160 to 200 Hz with a 1-octave bend, `mode` 1 with `mix` 2 to 4: the
  hit starts mostly tone and hands over to white or bright noise as the aux env falls (11 to 23 ms), then the
  noise rings on the main env (~120 ms).
  Copenhagen's brush snare uses dark noise and no click.
- **Claps:** `mode` 3, `bendtime` 3 (bursts 8.2 ms apart), `mix` 7 white noise, `decay` 8 to 9 tail.
  Tromsø's snare-clap is the same with `mix` 4 and a driven tone: the bursts are noise only, then the tail is
  half driven body, half noise. Snare and clap in one voice.
- **Hats:** noise only, bright (Default, Reykjavík open), white (Tromsø) or metal wave + metallic noise
  (Shoreditch); `decay` 5 closed (~15 ms), 8 open; channels 6 and 7 choke.
- **Shakers / jingle:** dark noise or metal in `mode` 3 with short burst spacing (`bendtime` 1 to 2: 2 to 4 ms),
  which gives a rattle instead of one click.
- **Ride, cowbell, ping, metal knock:** `wave` 3 (square XOR fixed squares) at 400 Hz to 2 kHz, with metallic or
  dark noise for the ride.
- **Woodblock, conga, bongos, toms:** triangle at 100 Hz to 1 kHz, 1-octave bend over 3 to 45 ms, `click` 1,
  decays from 8 ms (woodblock) to 0.3 s (low tom).
- **Zap:** square, `bend` 3 falling over 45 ms.
- **Ticks and glitch clicks:** decay 2 to 3 (2 to 4 ms), click on, bright noise or a square with a 3-octave
  1.4 ms bend.

## 5. Measured (model)

`python3 kits/tools/soundcheck.py` renders each channel alone through the model and prints the peak, the time to
-20 and -40 dB, the spectral centroid and the dominant frequency at 0 to 6 ms and 40 to 80 ms. Highlights:

| Sound | Start freq | 40-80 ms | -40 dB |
| --- | --- | --- | --- |
| Default kick | 282 Hz | 53 Hz | 247 ms |
| Reykjavík hammer kick | 290 Hz | 53 Hz | 304 ms |
| Shoreditch sub kick | 267 Hz | 46 Hz | 246 ms |
| Copenhagen deep kick | 168 Hz | 53 Hz | 312 ms |
| Default low / mid / high tom | 206 / 290 / 404 Hz | 114 / 168 / 229 Hz | 304 / 153 / 153 ms |
| Shoreditch zap | 1.1 kHz | 206 Hz | 144 ms |
| Reykjavík clap | — | — | 311 ms |
| Copenhagen tick | — | — | 5 ms |

Voice stealing (prototype allocation, same rule as the chip): the first patterns cut 6 to 34 hits each with 2
voices; after arranging the kits for 2 voices it is 0 to 2 per pattern (`kits/tools/steal.py`).

## 6. Tools

- `kits/tools/kitdefs.py`: the kits and patterns as code; writes `kits/*.json` and `kits/patterns/*.mid`.
- `kits/tools/render.py <id>`: renders a pattern through the model to `docs/v3/audio/<id>.mp3` (velocity scales
  `level`; ~20 s per pattern with numba).
- `kits/tools/steal.py`: voice-steal count and crowded steps per pattern.
- `kits/tools/soundcheck.py`: measurements.
