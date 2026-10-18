# SPDX-FileCopyrightText: © 2026 Juris Vitols
# SPDX-License-Identifier: Apache-2.0
"""UDS v3 tests: the chip is run window by window against model/uds3_model.py.

The model's Host decides, at the start of every 64-clock window, whether a
byte goes out (it waits for BUSY low after every HIT byte); the bench drives
the SPI pins so that the byte's internal pulse lands on the cycle the model
expects (Host.OFFSET). Every window it checks that the number of 1s on the
audio pin, BUSY, FRAME and the 7-segment digit equal the model's.
"""
import os
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "model"))
sys.path.insert(0, HERE)
import uds3_model as M  # noqa: E402

GL = os.environ.get("GATES") == "yes"
DIGITS = (0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07)
CS, MOSI, MISO, SCK, FRAME, BUSY = 0, 1, 2, 3, 4, 5
SCK_DIV = M.Host.SCK_DIV
GAP = M.Host.GAP


def byte_pins(start, value, first, last):
    """Pin changes {cycle: {pin: level}} for one byte starting at cycle start."""
    ch = {}
    if first:
        ch.setdefault(start - 6, {})[CS] = 0
    for i in range(8):
        bit = value >> (7 - i) & 1
        ch.setdefault(start + SCK_DIV * i, {}).update({SCK: 0, MOSI: bit})
        ch.setdefault(start + SCK_DIV * i + SCK_DIV // 2, {})[SCK] = 1
    ch.setdefault(start + 8 * SCK_DIV, {})[SCK] = 0
    if last:
        ch.setdefault(start + 8 * SCK_DIV + 4, {})[CS] = 1
    return ch


class Bench:
    def __init__(self, dut):
        self.dut = dut
        self.eng = M.Engine()
        self.host = M.Host()
        self.pins = {CS: 1, MOSI: 0, SCK: 0}
        self.sched = {}          # cycle -> pin changes
        self.msgs = {}           # frame -> [messages]
        self.errors = 0
        self.windows = 0
        self.bits_ones = []

    async def start(self):
        dut = self.dut
        cocotb.start_soon(Clock(dut.clk, 125, unit="ns").start())   # 8 MHz
        dut.ena.value = 1
        dut.ui_in.value = 0
        self.apply()
        dut.rst_n.value = 0
        await ClockCycles(dut.clk, 10)
        await FallingEdge(dut.clk)
        dut.rst_n.value = 1                       # this is cycle 0

    def apply(self):
        v = 0
        for p, lv in self.pins.items():
            v |= lv << p
        self.dut.uio_in.value = v

    def send(self, frame, msg):
        self.msgs.setdefault(frame, []).append(bytes(msg))

    def hit(self, frame, ch, patch):
        self.send(frame, M.hit_message(ch, patch))

    def stop(self, frame):
        self.send(frame, [0x40])

    async def run(self, frames, check_every=1):
        dut = self.dut
        cyc = 0
        expect = None            # (window, ones) to check once the tb latched it
        for n in range(2 * frames):
            w0 = n * 64
            if n % 2 == 0:
                for m in self.msgs.get(n // 2, ()):
                    self.host.send(m)
            # cycle w0: the decision
            assert int(dut.cyc.value) == w0, (int(dut.cyc.value), w0)
            busy_pin = int(dut.uio_out.value) >> BUSY & 1
            if busy_pin != int(self.eng.busy()):
                self.err(f"window {n}: BUSY {busy_pin}, model {int(self.eng.busy())}")
            msg_before = self.host.cur
            ev = self.host.next_event(self.eng.busy())
            if ev is not None:
                if ev[1] == "byte":
                    value = ev[3]
                elif ev[1] == "hit":
                    value = 0x18 | ev[2]
                else:
                    value = 0x40
                first = ev[1] != "byte"
                last = self.host.cur is None
                for c, ch in byte_pins(w0 + GAP, value, first, last).items():
                    self.sched.setdefault(c, {}).update(ch)
            ones = sum(self.eng.step_window(ev))
            # clock through the window, applying pin changes
            for c in range(w0, w0 + 64):
                if c != w0:
                    await FallingEdge(dut.clk)
                if c in self.sched:
                    self.pins.update(self.sched.pop(c))
                    self.apply()
                if c == w0 + 32:
                    out = int(dut.uio_out.value)
                    if (out >> FRAME & 1) != (1 - (n & 1)):
                        self.err(f"window {n}: FRAME {(out >> FRAME) & 1}")
                if c == w0 + 62:                  # after this window's pulse
                    seg = int(dut.uo_out.value) & 0x7F
                    if seg != DIGITS[self.eng.ch]:
                        self.err(f"window {n}: digit {seg:#x}, model ch {self.eng.ch}")
                if c == w0 + 1 and expect is not None:
                    got = int(dut.win_ones.value)
                    if got != expect[1]:
                        self.err(f"window {expect[0]} (frame {expect[0] // 2}): {got} ones, model {expect[1]}")
            expect = (n, ones)
            self.bits_ones.append(ones)
            self.windows += 1
            await FallingEdge(dut.clk)
        # last window
        await FallingEdge(dut.clk)
        got = int(dut.win_ones.value)
        if got != expect[1]:
            self.err(f"window {expect[0]}: {got} ones, model {expect[1]}")

    def err(self, s):
        self.errors += 1
        if self.errors <= 20:
            self.dut._log.error(s)


async def spi_read(b, reg):
    """READ with the bench's pin timing; returns the answer byte."""
    dut = b.dut
    out = 0
    seq = [0x30 | reg, 0x00]
    b.pins[CS] = 0
    b.apply()
    await ClockCycles(dut.clk, 4)
    for k, val in enumerate(seq):
        for i in range(8):
            await FallingEdge(dut.clk)
            b.pins.update({SCK: 0, MOSI: val >> (7 - i) & 1})
            b.apply()
            await ClockCycles(dut.clk, SCK_DIV // 2, rising=False)
            if k == 1:
                out = out << 1 | (int(dut.uio_out.value) >> MISO & 1)
            b.pins[SCK] = 1
            b.apply()
            await ClockCycles(dut.clk, SCK_DIV - SCK_DIV // 2, rising=False)
    b.pins.update({SCK: 0, CS: 1})
    b.apply()
    await ClockCycles(dut.clk, 4)
    return out


from schedules import kit_schedule, random_schedule  # noqa: E402


@cocotb.test()
async def test_id(dut):
    b = Bench(dut)
    await b.start()
    await ClockCycles(dut.clk, 300)
    idv = await spi_read(b, 0)
    ver = await spi_read(b, 1)
    dut._log.info(f"ID {idv:#04x} VERSION {ver:#04x}")
    assert idv == M.CHIP_ID, hex(idv)
    assert ver == M.VERSION, hex(ver)


@cocotb.test()
async def test_kit(dut):
    """A drum pattern: every voice feature, voice stealing, choke, STOP."""
    b = Bench(dut)
    await b.start()
    hits, stops, frames = kit_schedule(short=GL)
    for f, ch, p in hits:
        b.hit(f, ch, p)
    for f in stops:
        b.stop(f)
    await b.run(frames)
    dut._log.info(f"{b.windows} windows, {b.errors} errors")
    assert b.errors == 0


@cocotb.test(skip=GL)
async def test_random(dut):
    """Random patches at random times (all field values)."""
    b = Bench(dut)
    await b.start()
    hits, frames = random_schedule()
    for f, ch, p in hits:
        b.hit(f, ch, p)
    await b.run(frames)
    dut._log.info(f"{b.windows} windows, {b.errors} errors")
    assert b.errors == 0
