#!/usr/bin/env python3
"""Export model fixtures for the browser twin's truth test (V3-WEB).

For each schedule it writes test/fixtures/<name>.json:
  spi        pin changes [cycle, cs, sck, mosi] (cycle 0 = the first clock after
             reset; apply each change during that cycle, so the chip samples it
             on the rising edge that ends the cycle)
  windowOnes the number of 1s on the audio pin in each 64-clock window
  frameOnes  the same per 128-clock frame
  busy       the BUSY pin at the first clock of each window
  digit      the 7-segment channel at the last clock of each window
  crc32      zlib.crc32 of the whole bitstream (one byte 0/1 per clock)
The same host rules as test/test.py (model/uds3_model.py Host) produce the SPI.
"""
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "model"))
sys.path.insert(0, HERE)
import uds3_model as M  # noqa: E402
from schedules import kit_schedule, random_schedule  # noqa: E402


def byte_pins(start, value, first, last, sck_div=M.Host.SCK_DIV):
    ch = {}
    if first:
        ch.setdefault(start - 6, {})["cs"] = 0
    for i in range(8):
        ch.setdefault(start + sck_div * i, {}).update({"sck": 0, "mosi": value >> (7 - i) & 1})
        ch.setdefault(start + sck_div * i + sck_div // 2, {})["sck"] = 1
    ch.setdefault(start + 8 * sck_div, {})["sck"] = 0
    if last:
        ch.setdefault(start + 8 * sck_div + 4, {})["cs"] = 1
    return ch


def export(name, hits, stops, frames):
    msgs = {}
    for f, ch, p in hits:
        msgs.setdefault(f, []).append(M.hit_message(ch, p))
    for f in stops:
        msgs.setdefault(f, []).append(bytes([0x40]))
    eng, host = M.Engine(), M.Host()
    pins = {}
    bits = bytearray()
    win, busy, digit = [], [], []
    for n in range(2 * frames):
        if n % 2 == 0:
            for m in msgs.get(n // 2, ()):
                host.send(m)
        busy.append(int(eng.busy()))
        ev = host.next_event(eng.busy())
        if ev is not None:
            value = ev[3] if ev[1] == "byte" else (0x18 | ev[2]) if ev[1] == "hit" else 0x40
            for c, chg in byte_pins(n * 64 + M.Host.GAP, value, ev[1] != "byte", host.cur is None).items():
                pins.setdefault(c, {}).update(chg)
        b = eng.step_window(ev)
        bits += b
        win.append(sum(b))
        digit.append(eng.ch)
    state = {"cs": 1, "sck": 0, "mosi": 0}
    spi = []
    for c in sorted(pins):
        state.update(pins[c])
        spi.append([c, state["cs"], state["sck"], state["mosi"]])
    out = {
        "name": name, "contract": json.load(open(os.path.join(HERE, "..", "docs", "v3", "params.json")))["contract"],
        "clockHz": M.CLK_HZ, "windowClocks": 64, "frames": frames,
        "reset": "rst_n low for at least 10 clocks; cycle 0 is the clock in which rst_n goes high; "
                 "uio_in idle: CS high, SCK low, MOSI low",
        "spi": spi, "windowOnes": win,
        "frameOnes": [win[i] + win[i + 1] for i in range(0, len(win), 2)],
        "busy": busy, "digit": digit, "crc32": zlib.crc32(bytes(bits)) & 0xFFFFFFFF,
    }
    os.makedirs(os.path.join(HERE, "fixtures"), exist_ok=True)
    path = os.path.join(HERE, "fixtures", name + ".json")
    with open(path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(path, frames, "frames, crc", hex(out["crc32"]))


if __name__ == "__main__":
    export("uds3_kit", *kit_schedule())
    h, fr = random_schedule()
    export("uds3_random", h, [], fr)
