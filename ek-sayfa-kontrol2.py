#!/usr/bin/env python3
"""Aday "ek son sayfa"ları, dizinin son sayfasıyla kıyaslar (ikisi de aynı kaynaktan
çıkarılmış JPEG olduğu için kıyas adil).

Aynı içerikse → kopya, eklenmemeli. Farklıysa → uygulamanın gösterdiği ek sayfa olabilir.
"""
import subprocess

from PIL import Image, ImageChops

import atlas2pdf as a

ADAYLAR = [
    ('/Volumes/ATLAS/DVD1/2002/sayi2.bts', 144, 145),
    ('/Volumes/DVD2/DVD2/2004/sayi12.bts', 133, 134),
    ('/Volumes/DVD2/DVD2/2004/sayi5.bts', 158, 159),
    ('/Volumes/DVD2/DVD2/2004/sayi8.bts', 224, 225),
    ('/Volumes/DVD2/DVD2/2005/sayi11.bts', 101, 102),
]


def cikar(swf, n, fams, yol):
    cid = fams['p'].get((n, '')) or fams['page'].get((n, ''))
    if not cid:
        return None
    subprocess.run(['swfextract', '-j', str(cid), swf, '-o', yol], capture_output=True)
    try:
        return Image.open(yol)
    except Exception:
        return None


def fark(a, b):
    ga = a.convert('L').resize((64, 64))
    gb = b.convert('L').resize((64, 64))
    return sum(ImageChops.difference(ga, gb).getdata()) / 4096


def main():
    for swf, onceki, aday in ADAYLAR:
        images, sprites, exports, fams = a.page_images(swf)
        pa = cikar(swf, onceki, fams, '/tmp/a.jpg')
        pb = cikar(swf, aday, fams, '/tmp/b.jpg')
        etiket = f'{swf.split("/")[-2]}/{swf.split("/")[-1]}'
        if not pa or not pb:
            print(f'{etiket}: p{aday} çıkarılamadı (aile yok)')
            continue
        print(f'{etiket}: p{onceki} vs p{aday} ortalama fark {fark(pa, pb):.1f} '
              f'({pa.size} / {pb.size})')


if __name__ == '__main__':
    main()
