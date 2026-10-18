"""V3-SOUND prototype voice (NOT the chip model).

A quick, integer-only sketch of chip-friendly drum-voice features, used to rank
features and to draft kits before V3-CHIP's bit-exact model (model/uds3_model.py)
exists. It follows DRAFT 0 of docs/v3/CONTRACT.md plus a few experimental knobs
(marked X) that are candidates for CONTRACT 1.

Cheap-in-hardware rules kept here:
  * no per-sample multiplier: envelopes are applied as shift-and-add of a 4-bit
    level (what the chip does in time with 8x / 1x slots); here we multiply
    because it is the same number, and say so;
  * short integer state per voice: phase 16 b, env 8 b, aux env 8 b, timer bits;
  * all noise colours and the metal squares are GLOBAL (shared by all voices):
    one LFSR, one 1-pole low-pass, one difference high-pass, three counters.

fs = 62 500 Hz (one sample per frame). Output is float in -1..1 before the DAC;
the sigma-delta DAC itself is not modelled.
"""
import numpy as np

FS = 62500

DEFAULT = dict(pitch=64, decay=8, level=12, bend=0, bendtime=1, mix=0,
               wave=0, color=1, clap=0, snap=0,
               ndecay=None,   # X: separate noise decay (None = same as decay)
               split=0)       # X cheap alternative: 1 tone amp = min(env, aux), 2 noise amp = min(env, aux)

# bend -> peak pitch offset in steps: 0, 6, 12, 18, 24, 30, 36, 48 semitones
BEND_STEPS = [0, 16, 32, 48, 64, 80, 96, 128]

# bendtime -> aux-envelope step period in frames (env *= 7/8 per step)
# 7/8 per step = -1.16 dB; 30 dB ~ 26 steps.  2^k frames per step.
BENDTIME_SHIFT = [5, 6, 8, 9]      # step every 32..512 frames: offset falls to 1/4 in ~5, 11, 43, 85 ms


class Globals:
    """Shared per-frame sources: LFSR noise in colours, metal squares."""
    def __init__(self):
        self.lfsr = 0x7FFF
        self.lp = 0
        self.prev = 0
        self.t = 0

    def step(self):
        # 15-bit LFSR, x^15 + x^14 + 1, 8 shifts per frame -> 8-bit white sample
        v = 0
        for _ in range(8):
            b = ((self.lfsr >> 14) ^ (self.lfsr >> 13)) & 1
            self.lfsr = ((self.lfsr << 1) | b) & 0x7FFF
            v = (v << 1) | b
        white = v - 128                       # -128..127
        self.lp += (white - self.lp) >> 2     # dark: 1-pole LP, shift 2 (~2.5 kHz)
        dark = self.lp * 2                    # make up gain (still fits 9 b)
        bright = (white - self.prev) >> 1     # bright: first difference (HP, +6 dB/oct)
        self.prev = white
        # metal: XOR of 3 fixed squares at fs/6, fs/10, fs/14 (as v1) plus fs/17
        t = self.t
        m = ((t // 3) ^ (t // 5) ^ (t // 7)) & 1
        metal = 120 if m else -120
        self.t += 1
        return {0: dark, 1: white, 2: bright, 3: metal}, t


def tri(phase):            # 16-bit phase -> -256..255
    p = phase >> 7         # 9 bits
    return (p if p < 256 else 511 - p) * 2 - 256


def inc_of(pitch):         # v1: (32 + p[4:0]) << p[7:5]
    pitch = max(0, min(255, pitch))
    return (32 + (pitch & 31)) << (pitch >> 5)


class Voice:
    def __init__(self):
        self.env = 0
        self.ch = -1

    def hit(self, ch, patch):
        p = dict(DEFAULT); p.update(patch)
        self.p = p
        self.ch = ch
        self.env = 17 * p['level'] if p['level'] else 0   # 8-bit amp env
        self.nenv = self.env                               # X noise env
        self.aux = 255                                     # aux env: pitch bend
        self.phase = 0x4000
        self.age = 0                                       # frames since hit (timer bits)

    def step(self, G, gframe):
        if self.env == 0 and self.nenv == 0:
            return 0.0
        p = self.p
        # --- pitch: base + aux-env offset (shift only, no multiply) ---
        # bend b: offset = aux >> (7-b) * ... ; b=7 -> 0..~96 steps = +3 oct
        # bend b -> peak offset BEND_STEPS[b] pitch steps (32 / octave);
        # aux * const is a 2-3 term shift-add of the 8-bit aux env
        off = (self.aux * BEND_STEPS[p['bend']]) >> 8
        ph_inc = inc_of(p['pitch'] + off)
        self.phase = (self.phase + ph_inc) & 0xFFFF
        w = p['wave']
        t = tri(self.phase)
        if w == 0:
            tone = t
        elif w == 1:                       # driven: x2 then clip (shift + clamp)
            tone = max(-256, min(255, t * 2 + (t >> 1)))
        elif w == 2:
            tone = 255 if self.phase & 0x8000 else -256
        else:                              # metal: tone square XOR global metal square
            sq = 1 if self.phase & 0x8000 else 0
            m = 1 if G[3] > 0 else 0
            tone = 200 if sq ^ m else -200
        noise = G[p['color']]
        # --- clap gate: noise bursts at 0, ~10, ~20, ~30 ms, then tail ---
        ngate = 1.0
        if p['clap']:
            a = self.age
            if a < 4 * 640:                   # 4 bursts of 640 frames (10.2 ms)
                within = a % 640
                # each burst: decays fast inside its 10 ms (bit-level: aux of burst)
                ngate = max(0.0, 1 - within / 300.0)
            else:
                ngate = 1.0
        # --- snap: click transient, first (snap*16) frames, full scale ---
        click = 0
        if p['snap'] and self.age < p['snap'] * 12:
            click = 255 if self.age < p['snap'] * 6 else -256
        mix = p['mix']
        wt, wn = (7 - mix) / 7, mix / 7
        a_t = self.env / 255
        a_n = (self.nenv if p['ndecay'] is not None else self.env) / 255
        if p['split'] == 1:
            a_t = min(self.env, self.aux) / 255
        elif p['split'] == 2:
            a_n = min(self.env, self.aux) / 255
        out = (wt * tone * a_t + wn * noise * 2 * a_n * ngate + click * 0.8) / 256
        # --- envelopes (v1 rule: env -= max(env>>3,1) every 2^decay frames) ---
        self.age += 1
        if (gframe & ((1 << p['decay']) - 1)) == 0 and self.env:
            self.env -= max(self.env >> 3, 1)
        nd = p['ndecay'] if p['ndecay'] is not None else p['decay']
        if (gframe & ((1 << nd) - 1)) == 0 and self.nenv:
            self.nenv -= max(self.nenv >> 3, 1)
        if p['ndecay'] is None:
            self.nenv = self.env
        bs = BENDTIME_SHIFT[p['bendtime']]
        if (gframe & ((1 << bs) - 1)) == 0 and self.aux:
            self.aux -= max(self.aux >> 3, 1)
        return out


class Engine:
    def __init__(self, voices=2, choke=((6, 7),)):
        self.v = [Voice() for _ in range(voices)]
        self.G = Globals()
        self.choke = {}
        for grp in choke:
            for c in grp:
                self.choke[c] = grp[0]

    def hit(self, ch, patch):
        key = self.choke.get(ch, ch)
        for v in self.v:
            if v.ch >= 0 and self.choke.get(v.ch, v.ch) == key:
                return v.hit(ch, patch)
        for v in self.v:
            if v.env == 0 and getattr(v, 'nenv', 0) == 0:
                return v.hit(ch, patch)
        min(self.v, key=lambda v: max(v.env, v.nenv)).hit(ch, patch)

    def render(self, events, seconds):
        """events: list of (time_s, ch, patch), sorted."""
        n = int(seconds * FS)
        out = np.zeros(n)
        ei = 0
        for i in range(n):
            while ei < len(events) and events[ei][0] * FS <= i:
                self.hit(events[ei][1], events[ei][2]); ei += 1
            G, gf = self.G.step()
            out[i] = sum(v.step(G, gf) for v in self.v)
        return out


def one(patch, seconds=0.6):
    e = Engine(voices=1)
    return e.render([(0, 0, patch)], seconds)


def write_wav(path, x, fs=FS):
    from scipy.io import wavfile
    y = np.clip(x / max(1e-9, np.max(np.abs(x))) * 0.9, -1, 1)
    wavfile.write(path, fs, (y * 32767).astype(np.int16))
