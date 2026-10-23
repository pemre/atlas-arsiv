#!/usr/bin/env python3
"""Ham pageMask (düzeltme öncesi mantık) ile export edilen pN'leri kıyaslar.

page_plan artık maskenin ötesindeki export'ları kendisi eklediği için onunla
denetim yapılamıyor; burada swfdump -a çıktısı doğrudan okunur.

Çıktı: /tmp/fazla2.json (artımlı).
"""
import glob
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

CIKTI = '/tmp/fazla2.json'


def bak(f):
    out = subprocess.run(['swfdump', '-a', f], capture_output=True, text=True).stdout
    mask = None
    for line in out.splitlines():
        if '"pageMask"' in line and 'Push Lookup' in line:
            ad = re.findall(r'\((?:"([^"]*)"|-?\d+)\)', line)[1:]
            if ad and ad[-1] == 'Array':
                ad = ad[:-1]
            mask = list(reversed(ad))
            break
    if mask is None:
        return f, {'hata': 'pageMask yok'}
    mp = [int(m.group(1)) for s in mask if (m := re.fullmatch(r'p(\d+)', s))]
    ex = {int(m.group(1)) for m in re.finditer(r'exports \d+ as "p(\d+)"', out)}
    return f, {
        'mask': len(mask),
        'dummy': mask.count('dummy'),
        'mask_max': max(mp) if mp else 0,
        'exp_max': max(ex) if ex else 0,
        'fazla': sorted(ex - set(mp)),
        'son': mask[-2:],
    }


def main():
    veri = json.load(open(CIKTI)) if os.path.exists(CIKTI) else {}
    dosyalar = []
    for y in range(1993, 2006):
        for kok in ('/Volumes/ATLAS/DVD1', '/Volumes/DVD2/DVD2'):
            dosyalar += sorted(glob.glob(f'{kok}/{y}/sayi*.bts'))
    kalan = [f for f in dosyalar if f not in veri]
    print(f'{len(kalan)}/{len(dosyalar)} dosya', flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f, r in ex.map(bak, kalan):
            veri[f] = r
            json.dump(veri, open(CIKTI, 'w'), ensure_ascii=False)
    print('BİTTİ', len(veri), flush=True)


if __name__ == '__main__':
    main()
