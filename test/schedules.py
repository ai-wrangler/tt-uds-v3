"""Stimuli shared by the cocotb tests and the fixture export (make_fixtures.py)."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
import uds3_model as M  # noqa: E402

KICK = dict(pitch=12, decay=6, wave=1, bend=3, bendtime=3, mode=2, mix=1, color=0, level=15, click=1)
SNARE = dict(pitch=110, decay=5, wave=0, color=1, bend=1, bendtime=2, mode=1, mix=4, level=12)
CHAT = dict(pitch=0, decay=2, color=2, mix=7, level=10)
OHAT = dict(pitch=0, decay=5, color=3, mix=7, level=9)
CLAP = dict(pitch=0, decay=5, color=1, mix=7, mode=3, bendtime=1, level=13)
TOM = dict(pitch=70, decay=5, wave=0, bend=1, bendtime=4, level=13)
BELL = dict(pitch=150, decay=5, wave=3, level=11)
ZAP = dict(pitch=60, decay=4, wave=2, bend=3, bendtime=5, level=12)




def kit_schedule(short=False):
    """A drum pattern: every voice feature, voice stealing, choke, STOP.
    Returns (hits [(frame, ch, patch)], stops [frame], frames)."""
    seq = [(4, KICK), (6, CHAT), (0, SNARE), (6, CHAT), (7, OHAT), (6, CHAT), (5, CLAP),
           (2, TOM), (3, BELL), (1, ZAP), (4, KICK), (4, KICK)]
    step = 60 if short else 140
    f = 3
    hits = []
    for ch, p in seq:
        hits.append((f, ch, p))
        f += step
    stops = [f]
    hits.append((f + 20, 0, SNARE))
    return hits, stops, f + (80 if short else 400)


def random_schedule(seed=3, n=40):
    """Random patches (all field values) at random times."""
    rnd = random.Random(seed)
    f = 2
    hits = []
    for _ in range(n):
        hits.append((f, rnd.randrange(8), M.unpack([rnd.randrange(256) for _ in range(4)])))
        f += rnd.choice([1, 3, 8, 20, 60])
    return hits, f + 300
