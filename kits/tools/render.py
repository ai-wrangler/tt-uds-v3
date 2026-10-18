"""Render a kit's demo pattern to wav/mp3.

  python3 kits/tools/render.py <kit_id> [--engine proto|model] [--voices N]

engine=proto uses V3-SOUND's prototype (model/sound_proto.py, DRAFT 0 fields);
engine=model uses V3-CHIP's bit-exact model once model/uds3_model.py exists.
Velocity scales the patch level (level * vel / 127, rounded, at least 1), which
is what the controller is expected to do before sending a HIT.
"""
import argparse, json, os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'model'))
import kitdefs


def hits_for(kit_id):
    kit = json.load(open(os.path.join(ROOT, f'kits/{kit_id}.json')))
    nm = kitdefs.note_map(kit)
    patches = {c['ch']: c['patch'] for c in kit['channels']}
    ev, dur = kitdefs.events(kit_id)
    hits = []
    for t, n, v in ev:
        ch = nm[n]
        p = dict(patches[ch]); p['level'] = max(1, round(p['level'] * v / 127))
        hits.append((t, ch, p))
    return kit, hits, dur


def render(kit_id, engine='proto', voices=2, tail=1.0):
    kit, hits, dur = hits_for(kit_id)
    if engine == 'proto':
        import sound_proto as sp
        e = sp.Engine(voices=voices)
        return e.render(hits, dur + tail), sp.FS
    import uds3_model  # noqa: provided by V3-CHIP
    raise SystemExit('model engine: hook up once uds3_model.py exists')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kit'); ap.add_argument('--engine', default='proto')
    ap.add_argument('--voices', type=int, default=2); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    x, fs = render(a.kit, a.engine, a.voices)
    out = a.out or os.path.join(ROOT, f'docs/v3/audio/{a.kit}.mp3')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import sound_proto as sp
    wav = out.rsplit('.', 1)[0] + '.wav'
    sp.write_wav(wav, x, fs)
    if out.endswith('.mp3'):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-ar', '44100', '-b:a', '160k', out], check=True)
        os.remove(wav)
    print('wrote', out)


if __name__ == '__main__':
    main()
