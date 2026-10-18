# UDS v3 sound (V3-SOUND)

Status: **draft kits on DRAFT 0, rendered with the V3-SOUND prototype** (`model/sound_proto.py`), not yet
with V3-CHIP's bit-exact model. This file is updated when CONTRACT 1 and `model/uds3_model.py` land.

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

| Kit | Inspired by | Tempo | Intent |
| --- | --- | --- | --- |
| [Default](../../kits/default.json) | — | 124 | GM all-rounder: kick, snare, 3 toms, ride, closed/open hat |
| [Reykjavík](../../kits/reykjavik.json) | GusGus | 122 | Deep driven house: hammer kick, burst clap, shaker, bongos, rim, airy open hat |
| [Shoreditch](../../kits/shoreditch.json) | Simian Mobile Disco | 126 | Modular techno/electro: sub kick with noise click, electro snare, woodblock, conga, zap, cowbell, metal hats |
| [Copenhagen Night](../../kits/copenhagen.json) | Trentemøller | 120 | Dark minimal: deep long kick, trebly ticks and glitch clicks, brush snare, metal knock, dark ride |
| [Tromsø](../../kits/tromso.json) | Röyksopp | 116 | Warm crunchy pop-house: round driven kick, fat snare + clap, jingle, soft toms |

Demo patterns (original, 4 bars, GM drums on channel 10, tempo set): `kits/patterns/<id>.mid`.
Renders: `docs/v3/audio/<id>.mp3`.

## 4. How each sound is made (DRAFT 0 fields)

- **Kicks:** triangle (Default, Copenhagen) or driven triangle (Reykjavík, Tromsø) at 40 to 55 Hz, `bend` 4 to 6
  (+24 to +36 semitones) falling in ~10 to 40 ms (`bendtime` 1 to 2), `decay` 8 to 10 (0.1 to 0.4 s to
  -30 dB), `snap` 1 to 5 for the click.
- **Claps:** noise only (`mix` 7), white, `clap` on: 4 bursts ~10 ms apart then the tail (`decay` 8).
- **Snares:** triangle or square body at 160 to 200 Hz with a small bend, `mix` 4 to 6 noise, `snap` for the
  attack. Without a separate noise decay the body and the tail fade together (see the ranking, #2).
- **Hats:** noise only, `color` bright (high-passed) or metallic, `decay` 4 to 6 closed, 8 to 9 open;
  channels 6/7 choke.
- **Ride / cowbell / jingle / metal knock:** `wave` metal (tone square XOR fixed squares) mixed with metallic
  or dark noise.
- **Woodblock, conga, bongos, toms:** triangle at 100 Hz to 1 kHz with a small fast bend (1 to 3, `bendtime`
  0 to 2), short decays.
- **Zap:** square, `bend` 7 (+48 semitones) falling over ~40 ms.
- **Ticks / glitch clicks:** very short decay (1.7 to 3 ms), strong `snap`, bright or metallic noise.

## 5. Measured (prototype)

`python3 kits/tools/soundcheck.py` prints, per channel: level, time to -20/-40 dB, spectral centroid,
dominant frequency at 0 to 6 ms and 40 to 80 ms. Example: Default kick ~170 Hz at the start, 53 Hz at
40 to 80 ms, -40 dB after 280 ms.

Voice stealing with 2 voices cuts ~20 % of hits audibly in these patterns (3 voices: ~5 %); see the tracker.

## 6. Tools

- `kits/tools/kitdefs.py`: the kits and patterns as code; writes `kits/*.json` and `kits/patterns/*.mid`.
- `kits/tools/render.py <id>`: renders a pattern to `docs/v3/audio/<id>.mp3` (velocity scales `level`).
- `kits/tools/soundcheck.py`: measurements.
