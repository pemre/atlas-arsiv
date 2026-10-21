#!/usr/bin/env python3
"""Küçük kontroller: python3 test_atlas2pdf.py

SWF gerektirmeyen mantığı doğrular: sayı numaralandırma, siyah bar tespiti,
harita dilimi birleştirme (örtüşme bulma) ve PDF yazımı.
"""
import os
import tempfile

from PIL import Image, ImageDraw

import atlas2pdf as A


def test_issue_meta():
    # DVD düzeni: 1993'te sayi4 = Nisan 1993 = 1. sayı, sonrası aylık
    assert A.issue_meta('/x/DVD1/1993/sayi4.bts') == (1993, 4, 1)
    assert A.issue_meta('/x/DVD1/1993/sayi12.bts') == (1993, 12, 9)
    assert A.issue_meta('/x/DVD1/1994/sayi1.bts') == (1994, 1, 10)
    # 1999/sayi2 = Şubat 1999 = 71. sayı (bilinen dergi kapağıyla aynı)
    assert A.issue_meta('/x/DVD1/1999/sayi2.bts') == (1999, 2, 71)
    assert A.issue_meta('/x/DVD2/2003/Sayi1.bts') == (2003, 1, 118)
    assert A.issue_meta('/x/rastgele.bts') is None


def test_black_bars():
    im = Image.new('RGB', (400, 500), (0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([60, 0, 339, 499], fill=(20, 120, 60))      # ortada içerik
    l, r, box, top, bot = A.black_bars(im)
    assert (l, r) == (60, 60), (l, r)
    assert (top, bot) == (0, 0), (top, bot)
    assert box == (60, 0, 340, 500), box


def test_stitch_overlap():
    # aynı (tekrarsız) desenin kayan iki kopyası: 60 px örtüşme beklenir
    import random
    rnd = random.Random(42)
    base = Image.new('RGB', (540, 300))
    base.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
                  for _ in range(540 * 300)])
    a = base.crop((0, 0, 300, 300))
    b = base.crop((240, 0, 540, 300))          # 60 px örtüşme, eşit genişlik
    out = A.stitch([a, b])
    assert abs(out.width - 540) <= 12, out.width


def test_write_pdf():
    with tempfile.TemporaryDirectory() as d:
        files = []
        for i, color in enumerate([(200, 30, 30), (30, 200, 30), (30, 30, 200)]):
            f = os.path.join(d, f'{i}.jpg')
            Image.new('RGB', (80, 107), color).save(f, quality=90)
            files.append(f)
        pdf = os.path.join(d, 'x.pdf')
        A.write_pdf(files, pdf)
        data = open(pdf, 'rb').read()
        assert data.startswith(b'%PDF-1.4') and data.rstrip().endswith(b'%%EOF')
        assert b'/Count 3' in data                     # 3 sayfa
        assert data.count(b'/DCTDecode') == 3          # her sayfa JPEG olarak gömülü


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f'{name}: ok')
    print('hepsi geçti')
