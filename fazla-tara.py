#!/usr/bin/env python3
"""Her .bts için: pageMask'in kapsadığı en büyük p numarası vs export edilen en büyük p.

Amaç: maskede olmayan ama export edilmiş son sayfaları (uygulamanın son sayfa olarak
gösterdiği) bulmak. Çıktı: /tmp/fazla.json — artımlı yazılır.
"""
import glob
import json
import os
import re

import atlas2pdf as a

CIKTI = '/tmp/fazla.json'


def bak(f):
    try:
        images, sprites, exports, fams = a.page_images(f)
        plan = a.page_plan(f)
    except Exception as e:
        return f, {'hata': str(e)}
    mask_p = [int(m.group(1)) for x in plan if isinstance(x, str)
              and (m := re.fullmatch(r'p(\d+)_*', x))]
    exp_p = [int(m.group(1)) for x in exports
             if (m := re.fullmatch(r'p(\d+)_*', x))]
    return f, {
        'plan': len(plan),
        'mask_max': max(mask_p) if mask_p else 0,
        'exp_max': max(exp_p) if exp_p else 0,
        'son': plan[-3:],
        'fazla': sorted({n for n in exp_p if mask_p and n > max(mask_p)}),
    }


def main():
    veri = json.load(open(CIKTI)) if os.path.exists(CIKTI) else {}
    dosyalar = []
    for y in range(1993, 2006):
        for kok in ('/Volumes/ATLAS/DVD1', '/Volumes/DVD2/DVD2'):
            dosyalar += sorted(glob.glob(f'{kok}/{y}/sayi*.bts'))
    kalan = [f for f in dosyalar if f not in veri]
    print(f'{len(kalan)}/{len(dosyalar)} dosya', flush=True)
    for f in kalan:
        k, r = bak(f)
        veri[k] = r
        json.dump(veri, open(CIKTI, 'w'), ensure_ascii=False)
    print('BİTTİ', len(veri), flush=True)


if __name__ == '__main__':
    main()
