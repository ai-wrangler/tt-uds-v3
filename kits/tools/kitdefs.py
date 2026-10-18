"""V3-SOUND kit and pattern definitions -> kits/<id>.json and kits/patterns/<id>.mid.

Kits are written against the contract in docs/v3/params.json (field names are the
param ids there). Patterns are original 16-step grids, 4 bars each.
Run: python3 kits/tools/kitdefs.py
"""
import json, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARAMS = json.load(open(os.path.join(ROOT, 'docs/v3/params.json')))
CONTRACT = PARAMS['contract']
DEFAULTS = {p['id']: p['default'] for p in PARAMS['params']}


def P(**kw):
    """A full patch: contract defaults overridden by kw (unknown ids rejected)."""
    ids = {p['id']: p for p in PARAMS['params']}
    for k, v in kw.items():
        if k not in ids:
            raise KeyError(f'{k} not in contract {CONTRACT}')
        if not ids[k]['min'] <= v <= ids[k]['max']:
            raise ValueError(f'{k}={v} out of range')
    d = dict(DEFAULTS); d.update(kw)
    d.pop('res', None)
    return d


# ---------------------------------------------------------------- kits
KITS = []
# CONTRACT 1 cheat sheet (62.5 kHz frame):
#   pitch: 30.5 Hz * 2^(p/32)   (23 = 50 Hz, 59 = 110 Hz, 84 = 190 Hz, 99 = 260 Hz, 156 = 900 Hz)
#   decay: -30 dB after 30 * 2^d frames (5: 15 ms, 6: 31 ms, 7: 61 ms, 8: 123 ms, 9: 246 ms, 10: 0.5 s)
#   bend: 0..3 octaves; bendtime: aux to 1/4 in 1.4/2.8/5.6/11/23/45/90/180 ms (0..7)
#   mode: 0 same, 1 short tone (body), 2 short noise (click on a tone), 3 clap (bursts 64*2^bendtime frames apart)

KITS.append(dict(
    id='default', name='Default', inspiredBy='',
    description='A modern all-rounder on the General MIDI map: punchy pitched kick with a noise click, snappy '
                'snare (short body, longer noise), three tuned toms, metal ride, crisp hats.',
    tempo=124,
    channels=[
        dict(ch=0, name='Snare', notes=[37, 38, 39, 40],
             patch=P(pitch=84, decay=8, wave=0, color=1, bend=1, bendtime=4, mode=1, mix=4, level=15, click=1)),
        dict(ch=1, name='High tom', notes=[48, 50],
             patch=P(pitch=86, decay=8, wave=0, color=0, bend=1, bendtime=5, mode=0, mix=0, level=13, click=1)),
        dict(ch=2, name='Mid tom', notes=[45, 47],
             patch=P(pitch=70, decay=8, wave=0, color=0, bend=1, bendtime=5, mode=0, mix=0, level=13, click=1)),
        dict(ch=3, name='Low tom', notes=[41, 43],
             patch=P(pitch=54, decay=9, wave=0, color=0, bend=1, bendtime=5, mode=0, mix=0, level=13, click=1)),
        dict(ch=4, name='Kick', notes=[35, 36],
             patch=P(pitch=22, decay=9, wave=1, color=2, bend=3, bendtime=3, mode=2, mix=1, level=15, click=1)),
        dict(ch=5, name='Ride', notes=[51, 49, 52, 55, 57, 59],
             patch=P(pitch=170, decay=9, wave=3, color=3, bend=0, bendtime=0, mode=0, mix=4, level=9, click=0)),
        dict(ch=6, name='Closed hat', notes=[42, 44],
             patch=P(pitch=200, decay=5, wave=3, color=2, bend=0, bendtime=0, mode=0, mix=7, level=12, click=0)),
        dict(ch=7, name='Open hat', notes=[46],
             patch=P(pitch=200, decay=8, wave=3, color=2, bend=0, bendtime=0, mode=0, mix=7, level=11, click=0)),
    ]))

KITS.append(dict(
    id='reykjavik', name='Reykjavík', inspiredBy='GusGus',
    description='Inspired by GusGus: deep, driven house. A hard, saturated kick, a wide burst clap with a long '
                'tail, a dark shaker that chokes with an airy open hat, two bongo-like tuned hits, a rim and a '
                'metal ping.',
    tempo=122,
    channels=[
        dict(ch=0, name='Clap', notes=[39, 38, 40],
             patch=P(pitch=90, decay=9, wave=0, color=1, bend=0, bendtime=3, mode=3, mix=7, level=15, click=0)),
        dict(ch=1, name='Bongo high', notes=[60, 48, 50],
             patch=P(pitch=112, decay=6, wave=0, color=0, bend=1, bendtime=1, mode=0, mix=0, level=13, click=1)),
        dict(ch=2, name='Bongo low', notes=[61, 45, 47],
             patch=P(pitch=96, decay=7, wave=0, color=0, bend=1, bendtime=1, mode=0, mix=0, level=13, click=1)),
        dict(ch=3, name='Rim', notes=[37, 41, 43],
             patch=P(pitch=134, decay=4, wave=1, color=2, bend=1, bendtime=0, mode=2, mix=2, level=13, click=1)),
        dict(ch=4, name='Hammer kick', notes=[35, 36],
             patch=P(pitch=18, decay=9, wave=1, color=1, bend=3, bendtime=4, mode=2, mix=1, level=15, click=1)),
        dict(ch=5, name='Ping', notes=[56, 49, 51, 54],
             patch=P(pitch=150, decay=6, wave=3, color=3, bend=1, bendtime=0, mode=0, mix=1, level=10, click=1)),
        dict(ch=6, name='Shaker', notes=[42, 44, 70, 69, 82],
             patch=P(pitch=100, decay=6, wave=0, color=0, bend=0, bendtime=1, mode=3, mix=7, level=11, click=0)),
        dict(ch=7, name='Open hat', notes=[46],
             patch=P(pitch=220, decay=8, wave=3, color=2, bend=0, bendtime=0, mode=0, mix=7, level=11, click=0)),
    ]))

KITS.append(dict(
    id='shoreditch', name='Shoreditch', inspiredBy='Simian Mobile Disco',
    description='Inspired by Simian Mobile Disco: modular techno and electro. A tuned sub kick with a noise click, '
                'a snappy electro snare, woodblock and conga-like tuned hits, a laser zap, a cowbell and metal hats.',
    tempo=126,
    channels=[
        dict(ch=0, name='Electro snare', notes=[38, 40, 37],
             patch=P(pitch=90, decay=7, wave=2, color=2, bend=1, bendtime=2, mode=1, mix=5, level=15, click=1)),
        dict(ch=1, name='Woodblock', notes=[76, 77, 48, 50],
             patch=P(pitch=156, decay=4, wave=0, color=0, bend=1, bendtime=0, mode=0, mix=0, level=13, click=1)),
        dict(ch=2, name='Conga', notes=[62, 63, 64, 45, 47],
             patch=P(pitch=99, decay=7, wave=0, color=0, bend=1, bendtime=2, mode=0, mix=0, level=13, click=1)),
        dict(ch=3, name='Zap', notes=[41, 43, 39],
             patch=P(pitch=70, decay=8, wave=2, color=0, bend=3, bendtime=5, mode=0, mix=0, level=11, click=0)),
        dict(ch=4, name='Sub kick', notes=[35, 36],
             patch=P(pitch=20, decay=9, wave=0, color=1, bend=3, bendtime=3, mode=2, mix=2, level=15, click=1)),
        dict(ch=5, name='Cowbell', notes=[56, 49, 51],
             patch=P(pitch=134, decay=7, wave=3, color=3, bend=0, bendtime=0, mode=0, mix=0, level=10, click=1)),
        dict(ch=6, name='Metal hat', notes=[42, 44],
             patch=P(pitch=240, decay=5, wave=3, color=3, bend=0, bendtime=0, mode=0, mix=5, level=12, click=0)),
        dict(ch=7, name='Metal open hat', notes=[46],
             patch=P(pitch=240, decay=8, wave=3, color=3, bend=0, bendtime=0, mode=0, mix=5, level=11, click=0)),
    ]))

KITS.append(dict(
    id='copenhagen', name='Copenhagen Night', inspiredBy='Trentemøller',
    description='Inspired by Trentemøller: dark, minimal electronica. A soft long kick, trebly digital ticks, '
                'glitch clicks, a brushed noise snare, a low metal knock, a dark ride and an air hat that chokes '
                'the ticks.',
    tempo=120,
    channels=[
        dict(ch=0, name='Brush snare', notes=[38, 40, 37],
             patch=P(pitch=80, decay=8, wave=0, color=0, bend=0, bendtime=3, mode=1, mix=6, level=13, click=0)),
        dict(ch=1, name='Soft shaker', notes=[70, 48, 50],
             patch=P(pitch=100, decay=6, wave=0, color=0, bend=0, bendtime=1, mode=3, mix=7, level=9, click=0)),
        dict(ch=2, name='Glitch click', notes=[67, 68, 45, 47],
             patch=P(pitch=190, decay=3, wave=2, color=3, bend=3, bendtime=0, mode=0, mix=2, level=13, click=1)),
        dict(ch=3, name='Metal knock', notes=[41, 43],
             patch=P(pitch=104, decay=6, wave=3, color=3, bend=1, bendtime=1, mode=0, mix=1, level=12, click=1)),
        dict(ch=4, name='Deep kick', notes=[35, 36],
             patch=P(pitch=16, decay=9, wave=0, color=0, bend=2, bendtime=5, mode=0, mix=0, level=15, click=0)),
        dict(ch=5, name='Dark ride', notes=[51, 49, 59],
             patch=P(pitch=170, decay=10, wave=3, color=0, bend=0, bendtime=0, mode=0, mix=5, level=8, click=0)),
        dict(ch=6, name='Tick', notes=[42, 44, 75],
             patch=P(pitch=230, decay=2, wave=3, color=2, bend=0, bendtime=0, mode=0, mix=6, level=14, click=1)),
        dict(ch=7, name='Air hat', notes=[46],
             patch=P(pitch=250, decay=8, wave=0, color=2, bend=0, bendtime=0, mode=0, mix=7, level=10, click=0)),
    ]))

KITS.append(dict(
    id='tromso', name='Tromsø', inspiredBy='Röyksopp',
    description='Inspired by Röyksopp: warm, slightly crunchy electronic pop-house. A round driven kick, a snare-clap '
                '(burst clap over a driven body, one voice), a plain clap, a tambourine-like jingle, soft toms and '
                'a gentle open hat.',
    tempo=116,
    channels=[
        dict(ch=0, name='Snare-clap', notes=[38, 40, 37],
             patch=P(pitch=78, decay=8, wave=1, color=1, bend=1, bendtime=3, mode=3, mix=5, level=15, click=1)),
        dict(ch=1, name='Clap', notes=[39, 48, 50],
             patch=P(pitch=90, decay=8, wave=0, color=1, bend=0, bendtime=3, mode=3, mix=7, level=14, click=0)),
        dict(ch=2, name='Soft tom', notes=[45, 47],
             patch=P(pitch=70, decay=8, wave=0, color=0, bend=1, bendtime=5, mode=0, mix=0, level=13, click=0)),
        dict(ch=3, name='Low tom', notes=[41, 43],
             patch=P(pitch=56, decay=9, wave=0, color=0, bend=1, bendtime=5, mode=0, mix=0, level=13, click=0)),
        dict(ch=4, name='Round kick', notes=[35, 36],
             patch=P(pitch=24, decay=8, wave=1, color=0, bend=2, bendtime=4, mode=0, mix=0, level=15, click=1)),
        dict(ch=5, name='Jingle', notes=[54, 49, 51],
             patch=P(pitch=230, decay=7, wave=3, color=3, bend=0, bendtime=2, mode=3, mix=6, level=10, click=0)),
        dict(ch=6, name='Closed hat', notes=[42, 44],
             patch=P(pitch=210, decay=5, wave=0, color=1, bend=0, bendtime=0, mode=0, mix=7, level=12, click=0)),
        dict(ch=7, name='Open hat', notes=[46],
             patch=P(pitch=210, decay=8, wave=0, color=1, bend=0, bendtime=0, mode=0, mix=7, level=11, click=0)),
    ]))

# ---------------------------------------------------------------- patterns
# one line per GM note: 64 steps (4 bars of 16ths), 'x' = accent (vel 120), 'o' = normal (90),
# '.' = soft (55), '-' = rest. Spaces are ignored. All patterns are original.
PATTERNS = {
    'default': dict(swing=0.0, rows={
        36: 'x---x---x---x--- x---x---x---x--- x---x---x---x--- x---x---x--o-x-o',
        38: '----x-------x--- ----x-------x--- ----x-------x--- ----x-------x-.o',
        42: '--o---o---o---o- --o---o---o---o- --o---o---o---o- --o---o-o-o-o-o-',
        46: '---------------- ---------------- ---------------- ------------x---',
        51: 'o-------o------- o-------o------- o-------o------- o---------------',
        50: '---------------- ---------------- ---------------- ---------o------',
        47: '---------------- ---------------- ---------------- -----------o----',
        43: '---------------- ---------------- ---------------- -------------o--',
    }),
    'reykjavik': dict(swing=0.12, rows={
        36: 'x---x---x---x--- x---x---x---x--- x---x---x---x--- x---x---x---x-o-',
        39: '----x-------x--- ----x-------x--- ----x-------x--- ----x-------x--o',
        46: '--o---o---o---o- --o---o---o---o- --o---o---o---o- --o---o---o---x-',
        70: '-o.o-o.o-o.o-o.o -o.o-o.o-o.o-o.o -o.o-o.o-o.o-o.o -o.o-o.o-o.o-o--',
        60: '---------o------ -------o-------- ---------o------ -------o-o------',
        61: '-------------o-- -----------o---- -------------o-- -----------o-o--',
        37: '---------------- ---------o------ ---------------- -------------o--',
        56: '---------------- ----------o----- ---------------- ----------o-----',
    }),
    'shoreditch': dict(swing=0.0, rows={
        36: 'x---x---x---x--- x---x---x---x--- x---x---x---x--- x---x---x-x-x---',
        38: '----x-------x--- ----x-------x--- ----x-------x--- ----x--o----x-oo',
        42: 'o-x---x-o-x---x- o-x---x-o-x--ox- o-x---x-o-x---x- o-x---x-o-x-----',
        46: '---------------- ---------------x ---------------- --------------x-',
        76: '--o--o-------o-- --o--o-----o---- --o--o-------o-- --o--o---o-o----',
        62: '-------o-o------ ------o--o----o- -------o-o------ ------o--o-o-o--',
        41: '---------------- ----------o----- ---------------- --------------o-',
        56: '---o-------o---- ---o-------o---- ---o-------o---- ---o------------',
    }),
    'copenhagen': dict(swing=0.0, rows={
        36: 'x-------x------- x-------x-----.- x-------x------- x-------x---o---',
        38: '--------o------- --------o------- --------o------- --------o-----.o',
        42: '-o-o.-o--o-o.-o- -o-o.-o--o-o.-o- -o-o.-o--o-o.-o- -o-o.-o--o-o.---',
        46: '---------------- -------------o-- ---------------- --------------o-',
        67: '-----o---------- ----------o----- -----o---------- ---o-------o----',
        41: '---------o------ -------------o-- ---------o------ ------o---------',
        51: 'o--------------- ---------------- o--------------- ----------------',
    }),
    'tromso': dict(swing=0.08, rows={
        36: 'x-----o-x------- x-----o-x--o---- x-----o-x------- x-----o-x--o-o--',
        38: '----x-------x--- ----x-------x--- ----x-------x--- ----x-------x---',
        39: '---------------- ---------------- ---------------- -------------o-o',
        42: 'o-o---o-o-o---o- o-o---o-o-o---o- o-o---o-o-o---o- o-o---o-o-o-----',
        46: '------o-------o- ------o-------o- ------o-------o- ------o---------',
        54: '---------------o ---------------o ---------------o ----------------',
        47: '---------------- ---------------- ---------------- ---------o-o----',
        43: '---------------- ---------------- ---------------- ---------------o',
    }),
}
VEL = {'x': 120, 'o': 90, '.': 55}


def events(kit_id):
    """Pattern -> sorted list of (time_s, note, velocity)."""
    k = next(k for k in KITS if k['id'] == kit_id)
    pat = PATTERNS[kit_id]
    step = 60.0 / k['tempo'] / 4
    ev = []
    for note, row in pat['rows'].items():
        row = row.replace(' ', '')
        assert len(row) == 64, (kit_id, note, len(row))
        for i, c in enumerate(row):
            if c in VEL:
                t = i * step + (pat['swing'] * step if i % 2 else 0)
                ev.append((t, note, VEL[c]))
    ev.sort()
    return ev, 64 * step


def note_map(kit):
    m = {}
    for c in kit['channels']:
        for n in c['notes']:
            assert n not in m, (kit['id'], n, 'mapped twice')
            m[n] = c['ch']
    return m


# ---------------------------------------------------------------- MIDI writer (SMF type 0)
def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F)); n >>= 7
    return bytes(reversed(out))


def write_mid(path, kit, ev):
    tpq = 480
    us = int(60e6 / kit['tempo'])
    sec_per_tick = kit['tempo'] / 60.0 * tpq
    msgs = []
    for t, n, v in ev:
        tick = round(t * sec_per_tick)
        msgs.append((tick, 1, bytes([0x99, n, v])))
        msgs.append((tick + 60, 0, bytes([0x89, n, 0])))
    msgs.sort(key=lambda m: (m[0], m[1]))
    trk = b'\x00\xff\x51\x03' + us.to_bytes(3, 'big')
    trk += b'\x00\xff\x58\x04\x04\x02\x18\x08'
    name = f"UDS v3 {kit['name']}".encode('utf-8')
    trk += b'\x00\xff\x03' + vlq(len(name)) + name
    last = 0
    for tick, _, m in msgs:
        trk += vlq(tick - last) + m; last = tick
    end = 64 * tpq // 4
    trk += vlq(max(0, end - last)) + b'\xff\x2f\x00'
    data = b'MThd' + struct.pack('>IHHH', 6, 0, 1, tpq) + b'MTrk' + struct.pack('>I', len(trk)) + trk
    open(path, 'wb').write(data)


def main():
    os.makedirs(os.path.join(ROOT, 'kits/patterns'), exist_ok=True)
    for k in KITS:
        out = dict(id=k['id'], name=k['name'], inspiredBy=k['inspiredBy'], description=k['description'],
                   contract=CONTRACT, tempo=k['tempo'], pattern=f"patterns/{k['id']}.mid", channels=k['channels'])
        assert sorted(c['ch'] for c in k['channels']) == list(range(8))
        with open(os.path.join(ROOT, f"kits/{k['id']}.json"), 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
            f.write('\n')
        ev, _ = events(k['id'])
        nm = note_map(k)
        missing = {n for _, n, _ in ev if n not in nm}
        assert not missing, (k['id'], missing)
        write_mid(os.path.join(ROOT, f"kits/patterns/{k['id']}.mid"), k, ev)
        print('wrote', k['id'], len(ev), 'notes')


if __name__ == '__main__':
    main()
