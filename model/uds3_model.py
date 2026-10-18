"""UDS v3 golden model: the specification of record for the chip's sound engine.

The RTL (src/uds3_core.v, src/uds3_spi.v) must match this model exactly: for the
same SPI events it must put the same audio bit on the pin on every clock (the
tests compare the number of 1s per frame, and a CRC of the whole bitstream).

Architecture (see docs/v3/CONTRACT.md for the user-facing view)
    2 voices. Voice state lives in a 128-bit shift register (the ring): two
    64-bit words that move one bit per clock. One frame = 128 clocks, window 0
    (voice 0) then window 1 (voice 1), t = 0..63 within a window. At 8 MHz the
    frame rate is 62.5 kHz. Pitches and times are counted in frames, so they
    scale with the clock.

Voice word (fields; the bit layout is in the RTL header)
    pitch 8, decay 4, wave 2, color 2, bend 2, res 1, bendtime 3, mode 2, mix 3,
    ch 3, env 8, aux 8, phase 16

HIT = 0x18|ch, then P0..P3 (the host waits for BUSY low after every byte)
    P0 = pitch
    P1 = decay<<4 | wave<<2 | color
    P2 = bend<<6 | res<<5 | bendtime<<2 | mode
    P3 = mix<<5 | level<<1 | click

Timing of a HIT (cycle = clock index after reset, frame f = cycle // 128)
    * The command byte (a one-clock pulse inside the chip, see EVENT CYCLES)
      sets PEND. At the next frame end the target voice is chosen from the
      state at that frame end: the voice already playing the same channel
      (6 and 7 count as one), else a free voice (env = 0, voice 0 first), else
      the quieter one by env[7:5] (voice 0 on ties).
    * Each patch byte sets HV. At the next window end (after PEND is clear)
      that is followed by the target's window, the byte is written into the
      target's word during that window, and HV clears at its end.
      BUSY = PEND or HV.
    * P0 writes pitch and env = 0 (the voice goes silent).
      P1 writes decay, wave, color. P2 writes bend, res, bendtime, mode.
      P3 writes mix, ch, env = 17 x level, aux = 255, phase = 0x8000 if click
      else 0x4000. The voice sounds from the next frame on.

Per window (voice v of frame f), in RTL order
    1. Capture (on the last clock of the previous window, so with the frame
       counter value of that clock), from the stored word:
         tone  = waveform(phase[15:7], wave, frame bits)   8 bits signed
         meff  = eff_mix(mix, mode, aux)                   the noise share 0..7
         env, color, clap = (mode == 3)
    2. Step flags (clock 0, frame counter = f):
         env steps  if env != 0 and (tz(f) >= decay or tz(f) == 13)
         aux steps  if aux != 0 and tz(f) >= ad,   ad = bendtime if mode == 3 else bendtime + 3
       tz(f) = number of trailing zero bits of the 13-bit frame counter (13 if 0).
    3. Output: on clock t of the window the DAC gets x(t) (see window_x): the
       noise on the clocks the mix pattern gives it, the tone (0 in clap mode)
       on the rest; env >> 3 clocks at full value, env & 7 at 1/8, then 0.
    4. Update: env -= max(env >> 3, 1) (just 1 while env < 8), 0 after a STOP;
               aux -= max(aux >> 3, 1), or 1 in mode 3 (clap);
               a commit writes its fields;
               phase += (32 + pe[4:0]) << pe[7:5] (16 bits), with
               pe = min(255, pitch + bendoff(aux, bend)) from the values just
               written (new aux), unless P3 was written (phase = start).

Python's >> on negative ints is floor division, like Verilog's >>>.
"""

from __future__ import annotations

import struct
import zlib

CLK_HZ = 8_000_000
L = 64
FRAME = 128
FS = CLK_HZ / FRAME            # 62 500 Hz
CHIP_ID = 0xD5
VERSION = 0x32                 # 3 = v3, 2 voices
SPI_DELAY = 2                  # pin edge to internal pulse, in clocks (see tests)

FIELDS = ("pitch", "decay", "wave", "color", "bend", "res", "bendtime", "mode", "mix", "level", "click")


# ----------------------------------------------------------------- patches

def pack(p: dict) -> list[int]:
    """Patch dict -> [P0, P1, P2, P3]. Missing fields are 0."""
    g = lambda k: int(p.get(k, 0))
    return [g("pitch") & 255,
            (g("decay") & 15) << 4 | (g("wave") & 3) << 2 | (g("color") & 3),
            (g("bend") & 3) << 6 | (g("res") & 1) << 5 | ((g("bendtime") or g("btime")) & 7) << 2 | (g("mode") & 3),
            (g("mix") & 7) << 5 | (g("level") & 15) << 1 | (g("click") & 1)]


def unpack(b) -> dict:
    p0, p1, p2, p3 = b
    return dict(pitch=p0, decay=p1 >> 4, wave=p1 >> 2 & 3, color=p1 & 3,
                bend=p2 >> 6, res=p2 >> 5 & 1, bendtime=p2 >> 2 & 7, mode=p2 & 3,
                mix=p3 >> 5, level=p3 >> 1 & 15, click=p3 & 1)


def hit_message(ch: int, patch: dict) -> bytes:
    return bytes([0x18 | (ch & 7)] + pack(patch))


# ------------------------------------------------------------ voice math

def s9(v: int) -> int:
    v &= 0x1FF
    return v - 512 if v & 0x100 else v


def increment(pe: int) -> int:
    return (32 + (pe & 31)) << (pe >> 5)


def frequency(pe: int, fs: float = FS) -> float:
    return fs * increment(pe) / 65536.0


def bendoff(aux: int, bend: int) -> int:
    off = ((aux >> 1) if bend & 2 else 0) + ((aux >> 2) if bend & 1 else 0)
    return off >> 1


def eff_pitch(pitch: int, aux: int, bend: int) -> int:
    return min(255, pitch + bendoff(aux, bend))


def s8(v: int) -> int:
    v &= 0xFF
    return v - 256 if v & 0x80 else v


def triangle(ph: int) -> int:
    """8-bit signed triangle from phase[15:7]."""
    fold = (ph >> 7 & 0xFF) ^ (0xFF if ph & 0x8000 else 0)
    return s8(((~fold >> 7) & 1) << 7 | (fold & 0x7F))


def waveform(ph: int, wave: int, frame: int) -> int:
    tri = triangle(ph)
    if wave == 0:
        return tri
    if wave == 1:                                # driven: 2 x triangle, clipped
        return max(-128, min(127, 2 * tri))
    sq = ph >> 15 & 1
    if wave == 3:                                # metal: square XOR fs/2, fs/8 squares
        sq ^= (frame & 1) ^ (frame >> 2 & 1)
    return -128 if sq else 127


def eff_mix(mix: int, mode: int, aux: int) -> int:
    """The noise share actually used (0..7, 7 = noise only)."""
    a3 = aux >> 5
    if mode == 1:                                # short tone: the noise takes over
        return max(mix, 7 - a3)
    if mode == 2:                                # short noise: the noise share falls
        return min(mix, a3)
    if mode == 3:                                # clap: 3 bursts, then the tail
        return (aux >> 3 & 7) if aux >> 6 else mix
    return mix


def noise(color: int, lfsr: int, frame: int) -> int:
    if color == 0:                               # dark: 4-tap boxcar
        pc = bin(lfsr & 15).count("1")
        return 127 if pc == 4 else pc * 64 - 128
    if color == 1:                               # white
        return 127 if lfsr & 1 else -128
    if color == 2:                               # bright: first difference
        a, b = lfsr & 1, lfsr >> 1 & 1
        return 0 if a == b else (127 if a else -128)
    m = (frame >> 1 ^ frame >> 3 ^ frame >> 4) & 1   # metallic buzz
    return 127 if m else -128


def tz13(frame: int) -> int:
    f = frame & 0x1FFF
    if f == 0:
        return 13
    n = 0
    while not f & 1:
        f >>= 1
        n += 1
    return n


def sel_noise(t: int, mix: int) -> bool:
    if mix == 7:
        return True
    r = (t & 1) << 2 | (t & 2) | (t >> 2 & 1)
    return r < mix


def window_x(tone: int, nz: int, env: int, meff: int, clap: bool) -> list[int]:
    """The 64 DAC inputs of one window."""
    xs = []
    q, r = env >> 3, env & 7
    for t in range(L):
        sn = sel_noise(t, meff)
        src = nz if sn else (0 if clap else tone)
        if t < q:
            xs.append(src)
        elif t < q + r:
            xs.append(src >> 3)
        else:
            xs.append(0)
    return xs


def group(ch: int) -> int:
    return 6 if ch == 7 else ch


# ------------------------------------------------------------- the DAC

DAC_FB = 256


def _dac_py(xs, st):
    v1, v2 = st
    out = bytearray(len(xs))
    for i, x in enumerate(xs):
        y = 1 if v2 >= 0 else 0
        fb = DAC_FB if y else -DAC_FB
        out[i] = y
        v1, v2 = v1 + x - fb, v2 + v1 - 2 * fb
    st[0], st[1] = v1, v2
    return bytes(out)


_dac = _dac_py
try:                                             # optional speed-up
    import numba
    import numpy as _np

    @numba.njit(cache=True)
    def _dac_nb(xs, v1, v2, out):
        for i in range(xs.shape[0]):
            y = 1 if v2 >= 0 else 0
            fb = DAC_FB if y else -DAC_FB
            out[i] = y
            nv1 = v1 + xs[i] - fb
            v2 = v2 + v1 - 2 * fb
            v1 = nv1
        return v1, v2

    def _dac(xs, st):
        a = _np.asarray(xs, dtype=_np.int64)
        out = _np.zeros(a.shape[0], dtype=_np.uint8)
        st[0], st[1] = _dac_nb(a, st[0], st[1], out)
        return out.tobytes()
except Exception:                                # numba missing: pure Python
    pass


# ------------------------------------------------------------- the engine

class Voice:
    __slots__ = ("pitch", "decay", "wave", "color", "bend", "res", "bendtime", "mode", "mix",
                 "ch", "env", "aux", "phase")

    def __init__(self):
        for k in self.__slots__:
            setattr(self, k, 0)


class Engine:
    """Exact at window granularity.

    step_window(ev) runs one 64-clock window. ev is None or (offset, kind, ...),
    an internal one-clock pulse on cycle offset (0..62) of the window:
        (o, "hit", ch)      the HIT command byte 0x18|ch completed
        (o, "byte", k, b)   patch byte P(k-1) completed (k = 1..4), value b
        (o, "stop")         STOP completed
    Returns the window's 64 audio bits. busy() is the BUSY pin during the next
    window (BUSY changes only on window ends, one clock after a byte).
    """

    def __init__(self):
        self.v = [Voice(), Voice()]
        self.n = 0                    # windows run
        self.frame = 0                # 13-bit frame counter
        self.lfsr = 1
        self.dac = [0, -1]
        self.pend = False
        self.tgt = 0
        self.hv = False
        self.cb = 0
        self.rx = 0
        self.ch = 0                   # SPI channel register (last HIT)
        self.con = False              # this window writes the byte
        self.kill_pend = False
        self.kill = False

    def busy(self) -> bool:
        return self.pend or self.hv

    def step_window(self, ev=None):
        n = self.n
        vi = n & 1
        f = n >> 1
        clearing = f == 0
        voc = self.v[vi]
        # 1. capture, on the last clock of the previous window
        cap_frame = self.frame if vi == 1 else (self.frame - 1) & 0x1FFF
        tone = waveform(voc.phase, voc.wave, cap_frame)
        env0 = voc.env
        meff = eff_mix(voc.mix, voc.mode, voc.aux)
        clap = voc.mode == 3
        color = voc.color
        # 2. step flags, on clock 0
        tz = tz13(self.frame)
        dec = voc.env != 0 and (tz >= voc.decay or tz == 13)
        lin = voc.mode == 3
        ad = voc.bendtime if lin else voc.bendtime + 3
        adec = voc.aux != 0 and tz >= ad
        # 3. output
        if clearing:
            xs = [0] * L
        else:
            xs = window_x(tone, noise(color, self.lfsr, self.frame), env0, meff, clap)
        bits = _dac(xs, self.dac)
        # the pulse inside the window
        if ev is not None:
            kind = ev[1]
            if kind == "hit":
                self.pend = True
                self.ch = ev[2] & 7
            elif kind == "byte":
                self.hv = True
                self.cb = ev[2]
                self.rx = ev[3] & 255
            elif kind == "stop":
                self.kill_pend = True
        # 4. update the word as it passes
        if clearing:
            self.v[vi] = Voice()
        else:
            if dec:
                voc.env -= 1 if voc.env < 8 else voc.env >> 3
            if self.kill:
                voc.env = 0
            if adec:
                voc.aux -= 1 if (voc.aux < 8 or lin) else voc.aux >> 3
            p3 = self.con and self.cb == 4
            if self.con:
                self._commit(voc)
            if not p3:                        # the pitch from the bits just written
                pe = eff_pitch(voc.pitch, voc.aux, voc.bend)
                voc.phase = (voc.phase + increment(pe)) & 0xFFFF
        # 5. last clock of the window
        if self.hv and not self.pend and (1 - vi) == self.tgt:
            self.con = True
        elif self.con:
            self.con = False
            self.hv = False
        if vi == 1:
            a0, a1 = self.v[0].env != 0, self.v[1].env != 0
            self.kill = self.kill_pend
            self.kill_pend = False
            if self.pend:
                self.tgt = self._choose(a0, a1)
                self.pend = False
            if not a0 and not a1:
                self.dac[0], self.dac[1] = 0, -1
            self.lfsr = ((self.lfsr << 1) | ((self.lfsr >> 14 ^ self.lfsr >> 13) & 1)) & 0x7FFF   # x^15 + x^14 + 1
            self.frame = (self.frame + 1) & 0x1FFF
        self.n += 1
        return bits

    def _choose(self, a0, a1):
        hg = group(self.ch)
        v0, v1 = self.v
        if a0 and group(v0.ch) == hg:
            return 0
        if a1 and group(v1.ch) == hg:
            return 1
        if not a0:
            return 0
        if not a1:
            return 1
        return 1 if (v1.env >> 5) < (v0.env >> 5) else 0

    def _commit(self, voc):
        b, k = self.rx, self.cb
        if k == 1:
            voc.pitch = b
            voc.env = 0
        elif k == 2:
            voc.decay, voc.wave, voc.color = b >> 4, b >> 2 & 3, b & 3
        elif k == 3:
            voc.bend, voc.res, voc.bendtime, voc.mode = b >> 6, b >> 5 & 1, b >> 2 & 7, b & 3
        elif k == 4:
            voc.mix = b >> 5
            voc.ch = self.ch
            voc.env = (b >> 1 & 15) * 17
            voc.aux = 255
            voc.phase = 0x8000 if b & 1 else 0x4000


# --------------------------------------------------------------- the host

class Host:
    """The standard host, as the tests and the browser twin drive the chip.

    Messages go out one byte per window at most: a byte starts GAP clocks
    into a window and its internal pulse comes on cycle OFFSET of that window
    (OFFSET = GAP + 8 * SCK_DIV - SCK_DIV // 2 + SPI_DELAY, with SCK_DIV = 6).
    After each byte of a HIT the host waits for BUSY low; a byte goes out in
    the first window that starts with BUSY low. After a STOP it waits one
    window. CS goes high after the last byte of each message.
    """
    SCK_DIV = 6
    GAP = 8
    OFFSET = GAP + 8 * SCK_DIV - SCK_DIV // 2 + SPI_DELAY   # 55

    def __init__(self):
        self.q = []                 # pending messages (bytes)
        self.cur = None
        self.i = 0

    def send(self, msg: bytes):
        self.q.append(bytes(msg))

    def idle(self):
        return self.cur is None and not self.q

    def next_event(self, busy: bool):
        """Called at each window start; returns the pulse for this window."""
        if busy:
            return None
        if self.cur is None:
            if not self.q:
                return None
            self.cur, self.i = self.q.pop(0), 0
        msg, i = self.cur, self.i
        if i == 0:
            ev = (self.OFFSET, "stop") if msg[0] == 0x40 else (self.OFFSET, "hit", msg[0] & 7)
        else:
            ev = (self.OFFSET, "byte", i, msg[i])
        self.i += 1
        if self.i >= len(msg):
            self.cur = None
        return ev


def run(hits, frames, stops=()):
    """hits: iterable of (frame, ch, patch dict); stops: frames of STOPs.
    A message is queued at the start of its frame and goes out when the host
    is free. Returns (bits: bytes, events: list of (window, event))."""
    sched = {}
    for f, ch, patch in hits:
        sched.setdefault(f, []).append(hit_message(ch, patch))
    for f in stops:
        sched.setdefault(f, []).append(bytes([0x40]))
    eng, host = Engine(), Host()
    out = bytearray()
    evlog = []
    for f in range(frames):
        for m in sched.get(f, ()):
            host.send(m)
        for _ in range(2):
            ev = host.next_event(eng.busy())
            if ev is not None:
                evlog.append((eng.n, ev))
            out += eng.step_window(ev)
    return bytes(out), evlog


def frame_counts(bits: bytes) -> list[int]:
    return [sum(bits[i:i + FRAME]) for i in range(0, len(bits), FRAME)]


def crc(bits: bytes) -> int:
    return zlib.crc32(bytes(bits)) & 0xFFFFFFFF
