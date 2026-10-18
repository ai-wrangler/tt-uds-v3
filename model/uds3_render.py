#!/usr/bin/env python3
"""Render UDS v3 to a WAV file, bit-exact through the chip model.

The chip's audio pin (model/uds3_model.py, 1 bit per 8 MHz clock) goes through
the RC filter of the DIY guide (1 kOhm, 10 nF: tau = 10 us, -3 dB at 15.9 kHz),
then a 125-clock average (64 kHz) and a 3/4 polyphase resampler to 48 kHz.

Usage
    python3 model/uds3_render.py song.json out.wav
        song.json: {"patches": {"0": {...}, ...},           # per channel (CONTRACT 1 ids)
                    "hits": [[time_s, ch], [time_s, ch, {"level": 9}], ...],
                    "seconds": 4.0}                          # optional
    python3 model/uds3_render.py --kit kits/reykjavik.json --mid kits/patterns/reykjavik.mid out.wav
        (GM notes mapped by the kit's "notes" lists or the default map;
         level scaled by velocity / 127, at least 1; needs mido)

API
    render_wav(hits, seconds, path)   hits = [(time_s, ch, patch dict), ...]
    render_pcm(hits, seconds)         -> float32 numpy array at 48 kHz
"""

import argparse
import json
import math
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uds3_model as M  # noqa: E402

RATE = 48_000
TAU = 1e3 * 10e-9                     # RC: 1 kOhm x 10 nF
GM_MAP = {35: 4, 36: 4, 37: 0, 38: 0, 39: 0, 40: 0, 41: 3, 43: 3, 45: 2, 47: 2, 48: 1, 50: 1,
          42: 6, 44: 6, 46: 7, 49: 5, 51: 5, 52: 5, 55: 5, 57: 5, 59: 5}


def bits_to_pcm(bits: bytes) -> np.ndarray:
    from scipy.signal import lfilter, resample_poly
    b = np.frombuffer(bits, dtype=np.uint8).astype(np.float64) - 0.5
    a = 1.0 - math.exp(-1.0 / (M.CLK_HZ * TAU))
    y, _ = lfilter([a], [1.0, a - 1.0], b, zi=[0.0]) if len(b) else (b, None)
    n = len(y) // 125 * 125
    y64 = y[:n].reshape(-1, 125).mean(axis=1)          # 64 kHz
    y48 = resample_poly(y64, 3, 4)
    return y48.astype(np.float32)


def render_pcm(hits, seconds):
    frames = int(seconds * M.FS) + 1
    fh = [(int(round(t * M.FS)), ch, p) for t, ch, p in hits]
    bits, _ = M.run(fh, frames)
    return bits_to_pcm(bits)


def write_wav(path, pcm, gain=8.0):
    pcm = np.clip(pcm * gain, -1.0, 1.0)
    data = (pcm * 32767).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)


def render_wav(hits, seconds, path, gain=8.0):
    pcm = render_pcm(hits, seconds)
    write_wav(path, pcm, gain)
    return pcm


def hits_from_song(song):
    patches = {int(k): v for k, v in song["patches"].items()}
    hits = []
    for h in song["hits"]:
        t, ch = float(h[0]), int(h[1])
        p = dict(patches.get(ch, {}))
        if len(h) > 2:
            p.update(h[2])
        hits.append((t, ch, p))
    secs = song.get("seconds") or (max((h[0] for h in hits), default=0) + 1.0)
    return hits, secs


def hits_from_kit_mid(kit, mid_path, loops=1):
    import mido
    notemap = dict(GM_MAP)
    for c in kit["channels"]:
        for n in c.get("notes", []):
            notemap[n] = c["ch"]
    patches = {c["ch"]: c["patch"] for c in kit["channels"]}
    mf = mido.MidiFile(mid_path)
    t, ev = 0.0, []
    for msg in mf:                      # iterating a MidiFile yields seconds
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0 and msg.note in notemap:
            ch = notemap[msg.note]
            p = dict(patches[ch])
            p["level"] = max(1, round(p.get("level", 12) * msg.velocity / 127))
            ev.append((t, ch, p))
    length = mf.length
    hits = [(t + k * length, ch, p) for k in range(loops) for t, ch, p in ev]
    return hits, loops * length + 1.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("song", nargs="?", help="song.json (patches + hits)")
    ap.add_argument("out", help="output .wav")
    ap.add_argument("--kit")
    ap.add_argument("--mid")
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--gain", type=float, default=8.0)
    a = ap.parse_args()
    if a.kit:
        hits, secs = hits_from_kit_mid(json.load(open(a.kit)), a.mid, a.loops)
    else:
        hits, secs = hits_from_song(json.load(open(a.song)))
    pcm = render_wav(hits, secs, a.out, a.gain)
    print(f"{a.out}: {len(pcm) / RATE:.2f} s, peak {np.abs(pcm).max() * a.gain:.2f}")


if __name__ == "__main__":
    main()
