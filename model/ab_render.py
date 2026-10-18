#!/usr/bin/env python3
"""A/B render: the same MIDI pattern on UDS v2 (sd2) and on UDS v3.

v2: model/uds_model.py (2 voices, 6 MHz, its 8 drum presets, as the chip's
pin triggers would play them). v3: model/uds3_model.py with a kit from kits/.
Both go clock by clock through their own sigma-delta DAC, the 1 kOhm / 10 nF RC
filter, and down to 48 kHz (model/uds3_render.py). The output file has v2
first, 0.6 s of silence, then v3, at the same gain.

    python3 model/ab_render.py kits/default.json kits/patterns/default.mid docs/v3/audio/ab_default.mp3
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uds3_model as M3  # noqa: E402
import uds3_render as R  # noqa: E402
import uds_model as M2  # noqa: E402


def pcm_from_bits(bits, clk, decim):
    from scipy.signal import lfilter, resample_poly
    b = np.asarray(bits, dtype=np.float64) - 0.5
    a = 1.0 - math.exp(-1.0 / (clk * R.TAU))
    y = lfilter([a], [1.0, a - 1.0], b)
    n = len(y) // decim * decim
    y = y[:n].reshape(-1, decim).mean(axis=1)
    rate = clk / decim
    if rate != R.RATE:
        y = resample_poly(y, int(R.RATE), int(rate))
    return y.astype(np.float32)


def v2_pcm(hits, seconds):
    """hits: (time_s, ch, velocity). v2 plays its preset for the channel."""
    fs = 6_000_000 / 96
    frames = int(seconds * fs) + 1
    ev = sorted((int(round(t * fs)), ch, vel) for t, ch, vel in hits)
    eng = M2.Engine(2, triggers=False, status=False)
    eng.bits = []
    k, last = 0, -2
    for f in range(frames):
        if k < len(ev) and ev[k][0] <= f and f - last >= 2:
            _, ch, vel = ev[k]
            pitch, sweep, decay, balance, level = M2.PRESETS[ch]
            level = max(1, round(level * vel / 127))
            eng.hit(ch, M2.hit_bytes(pitch, sweep, decay, balance, level))
            last = f
            k += 1
        eng.step()
    return pcm_from_bits(eng.bits, 6_000_000, 125)


def v3_pcm(hits, seconds):
    frames = int(seconds * M3.FS) + 1
    fh = [(int(round(t * M3.FS)), ch, p) for t, ch, p in hits]
    bits, _ = M3.run(fh, frames)
    return pcm_from_bits(np.frombuffer(bits, dtype=np.uint8), M3.CLK_HZ, 125)


def main():
    kit_path, mid_path, out = sys.argv[1:4]
    kit = json.load(open(kit_path))
    hits3, secs = R.hits_from_kit_mid(kit, mid_path, loops=2)
    # the same notes with their velocities for v2
    import mido
    notemap = dict(R.GM_MAP)
    for c in kit["channels"]:
        for n in c.get("notes", []):
            notemap[n] = c["ch"]
    mf = mido.MidiFile(mid_path)
    t, hits2 = 0.0, []
    for msg in mf:
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0 and msg.note in notemap:
            hits2.append((t, notemap[msg.note], msg.velocity))
    hits2 = [(tt + k * mf.length, ch, v) for k in range(2) for tt, ch, v in hits2]
    a = v2_pcm(hits2, secs)
    b = v3_pcm(hits3, secs)
    gain = 0.9 / max(np.abs(a).max(), np.abs(b).max())
    pcm = np.concatenate([a, np.zeros(int(0.6 * R.RATE), np.float32), b])
    wav = out[:-4] + ".wav" if out.endswith(".mp3") else out
    R.write_wav(wav, pcm, gain)
    if out.endswith(".mp3"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "160k", out], check=True)
        os.remove(wav)
    print(out, f"v2 {len(a) / R.RATE:.1f} s + v3 {len(b) / R.RATE:.1f} s, gain {gain:.1f}")


if __name__ == "__main__":
    main()
