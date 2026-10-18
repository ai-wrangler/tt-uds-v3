"""Count audible voice steals (victim above -16 dB) per kit for N voices, by victim<-thief channel."""
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'model'))
import sound_proto as sp, render
orig = sp.Engine.hit
def hit(self, ch, p):
    before = [(v.ch, max(v.env, v.nenv), id(getattr(v, 'p', None))) for v in self.v]
    orig(self, ch, p)
    for (c, l, i), v in zip(before, self.v):
        if id(getattr(v, 'p', None)) != i and l > 40 and self.choke.get(c, c) != self.choke.get(ch, ch):
            self.stats[(c, ch)] += 1
sp.Engine.hit = hit
def steals(kit_id, voices=2):
    kit, hits, dur = render.hits_for(kit_id)
    e = sp.Engine(voices=voices); e.stats = collections.Counter()
    e.render(hits, dur)
    names = {c['ch']: c['name'] for c in kit['channels']}
    return len(hits), sum(e.stats.values()), {f"{names[a]}<-{names[b]}": n for (a, b), n in e.stats.most_common()}
if __name__ == '__main__':
    for k in sys.argv[1:] or ['default', 'reykjavik', 'shoreditch', 'copenhagen', 'tromso']:
        print(k, steals(k))


def crowded(kit_id):
    """Steps where more than 2 voice groups start at once (chip has 2 voices; 6/7 share one)."""
    import kitdefs, json
    kit = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), f'kits/{kit_id}.json')))
    nm = kitdefs.note_map(kit)
    rows = kitdefs.PATTERNS[kit_id]['rows']
    out = []
    for i in range(64):
        g = {min(nm[n], 6) if nm[n] >= 6 else nm[n] for n, r in rows.items() if r.replace(' ', '')[i] != '-'}
        if len(g) > 2:
            out.append(i)
    return out
