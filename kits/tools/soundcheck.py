"""Measure every channel of every kit (solo hit): peak level, time to -20/-40 dB,
spectral centroid, dominant frequency in the first 5 ms and at 40-80 ms.
  python3 kits/tools/soundcheck.py [--png out.png]
"""
import json, os, sys, glob
import numpy as np, scipy.signal as ss
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'model'))
sys.path.insert(0, HERE)
import render
FS = 62500

def solo(patch, sec=0.8, engine='model'):
    x, _ = render.render_hits([(0.001, 0, patch)], sec, engine)
    return x

def metrics(x):
    e = ss.filtfilt(*ss.butter(2, 150 / (FS / 2)), np.abs(x))
    pk = e.max() + 1e-12
    t = lambda db: (np.argmax(e < pk * 10 ** (db / 20) * (np.arange(len(e)) > np.argmax(e))) / FS * 1000)
    def domf(a, b):
        seg = x[int(a * FS / 1000):int(b * FS / 1000)]
        if len(seg) < 16 or np.abs(seg).max() < 1e-6: return 0
        n = 8192; S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
        return np.fft.rfftfreq(n, 1 / FS)[np.argmax(S[3:]) + 3]
    S = np.abs(np.fft.rfft(x[:int(0.1 * FS)])) ** 2; f = np.fft.rfftfreq(int(0.1 * FS), 1 / FS)
    cen = (S * f).sum() / (S.sum() + 1e-12)
    return dict(peak=20*np.log10(np.abs(x).max()+1e-9), rms=20*np.log10(np.sqrt((x[:int(.1*FS)]**2).mean())+1e-9), t20=t(-20), t40=t(-40),
                cent=cen, f0=domf(0, 6), f1=domf(40, 80))

if __name__ == '__main__':
    pngs = []
    for path in sorted(glob.glob(os.path.join(ROOT, 'kits/*.json'))):
        kit = json.load(open(path)); print(f"== {kit['id']}")
        for c in kit['channels']:
            m = metrics(solo(c['patch']))
            print(f"  ch{c['ch']} {c['name']:16s} pk{m['peak']:6.1f} rms{m['rms']:6.1f}dB  -20dB {m['t20']:6.1f}ms  -40dB {m['t40']:6.1f}ms"
                  f"  centroid {m['cent']:6.0f}Hz  f(0-6ms) {m['f0']:6.0f}  f(40-80ms) {m['f1']:6.0f}")
