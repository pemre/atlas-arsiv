#!/usr/bin/env python3
"""Maskenin ardından gelen (max+1) export'ları mevcut PDF'in son sayfasıyla kıyaslar.

Kullanım: python3 ek-sayfa-kontrol.py
Çıktı: /tmp/ek/ altında <ad>_ek.jpg (yeni sayfa) ve <ad>_pdf.png (şu anki son sayfa).
"""
import os
import subprocess

import numpy as np
import pymupdf
from PIL import Image

import atlas2pdf as a

DOSYALAR = [
    ('/Volumes/ATLAS/DVD1/2002/sayi2.bts', '2002-02 Atlas Dergisi 107.pdf'),
    ('/Volumes/DVD2/DVD2/2004/sayi12.bts', '2004-12 Atlas Dergisi 141.pdf'),
    ('/Volumes/DVD2/DVD2/2004/sayi5.bts', '2004-05 Atlas Dergisi 134.pdf'),
    ('/Volumes/DVD2/DVD2/2004/sayi8.bts', '2004-08 Atlas Dergisi 137.pdf'),
    ('/Volumes/DVD2/DVD2/2005/sayi11.bts', '2005-11 Atlas Dergisi 152.pdf'),
]
ARSIV = '/Volumes/ebook/dergi/Atlas'
CIKTI = '/tmp/ek'


def vektor(im):
    im = im.convert('L').resize((48, 48))
    v = np.asarray(im, dtype=float).ravel()
    return v / (np.linalg.norm(v) + 1e-9)


def main():
    os.makedirs(CIKTI, exist_ok=True)
    for swf, pdf in DOSYALAR:
        etiket = pdf.split(' Atlas')[0]
        images, sprites, exports, fams = a.page_images(swf)
        plan = a.page_plan(swf)
        mask_p = [int(m.group(1)) for s in plan if s and (m := __import__('re').fullmatch(r'p(\d+)', s))]
        n = max(mask_p)          # page_plan sona eklediyse bu, eklenen sayfa
        cid = fams['p'].get((n, '')) or fams['page'].get((n, ''))
        print(f'{etiket}: aday p{n} cid={cid}')
        jpg = f'{CIKTI}/{etiket}_ek.jpg'
        subprocess.run(['swfextract', '-j', str(cid), swf, '-o', jpg], capture_output=True)
        yeni = Image.open(jpg)
        d = pymupdf.open(f'{ARSIV}/{pdf}')
        son = d[len(d) - 1]
        pix = son.get_pixmap(dpi=40)
        eski = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        eski.save(f'{CIKTI}/{etiket}_pdf.png')
        benzerlik = float(vektor(yeni) @ vektor(eski))
        print(f'{etiket}: ek p{n} {yeni.size}, PDF {len(d)} sayfa, son sayfa benzerlik {benzerlik:.3f}')


if __name__ == '__main__':
    main()
