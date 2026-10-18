"""Render a kit's demo pattern to mp3 (or wav).

  python3 kits/tools/render.py <kit_id> [--engine model|proto] [--out path]

engine=model (default) runs V3-CHIP's bit-exact model (model/uds3_model.py): the
standard Host sends each HIT with the BUSY wait after every byte, and the audio
is the number of 1s on the pin per 128-clock frame (62.5 kHz), minus the idle 64.
That is the chip's sigma-delta output through a 128-clock boxcar; save() then
applies the board's RC filter (1 kOhm + 10 nF) and normalizes the peak. engine=proto uses V3-SOUND's DRAFT 0 prototype (old kits only).

Velocity scales the patch level (level * vel / 127, rounded, at least 1), which is
what the controller is expected to do before it sends a HIT.
"""
import argparse, json, os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'model'))
import kitdefs

# params.json id -> uds3_model field name (where they differ)
MODEL_NAME = {'bendtime': 'btime'}


def model_patch(p):
    return {MODEL_NAME.get(k, k): v for k, v in p.items()}


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


def render_hits(hits, seconds, engine='model'):
    if engine == 'proto':
        import sound_proto as sp
        return sp.Engine(voices=2).render(hits, seconds), sp.FS
    import uds3_model as m
    fs = int(m.FS)
    mh = [(int(round(t * fs)), ch, model_patch(p)) for t, ch, p in hits]
    bits, _ = m.run(mh, int(seconds * fs))
    x = np.frombuffer(bits, dtype=np.uint8).reshape(-1, m.FRAME).sum(axis=1).astype(float) - m.FRAME / 2
    return x / (m.FRAME / 2), fs


def render(kit_id, engine='model', tail=1.0):
    kit, hits, dur = hits_for(kit_id)
    return render_hits(hits, dur + tail, engine)


def save(x, fs, out):
    from scipy.io import wavfile
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    # the board's RC filter (1 kOhm + 10 nF, fc = 15.9 kHz), one pole at the 62.5 kHz frame rate
    import scipy.signal as ss
    y = ss.lfilter(*ss.butter(1, 15915 / (fs / 2)), x - np.mean(x))
    y = np.clip(y / max(1e-9, np.max(np.abs(y))) * 0.89, -1, 1)
    wav = out.rsplit('.', 1)[0] + '.wav'
    wavfile.write(wav, fs, (y * 32767).astype(np.int16))
    if out.endswith('.mp3'):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-ar', '44100', '-b:a', '192k', out], check=True)
        os.remove(wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kit'); ap.add_argument('--engine', default='model'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    x, fs = render(a.kit, a.engine)
    out = a.out or os.path.join(ROOT, f'docs/v3/audio/{a.kit}.mp3')
    save(x, fs, out)
    print('wrote', out)


if __name__ == '__main__':
    main()
