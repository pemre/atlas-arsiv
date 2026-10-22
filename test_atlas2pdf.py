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


def test_page_plan():
    """bts'nin kendi sayfa dizisi: 1. sayının siyah dolguları elle doğrulanmış hâliyle
    birebir olmalı (kullanıcının basılı dergiyle karşılaştırıp sıraladığı PDF)."""
    bts = '/Volumes/ATLAS/DVD1/1993/sayi4.bts'
    if not os.path.exists(bts):
        print('  (atlandı: DVD bağlı değil)')
        return
    plan = A.page_plan(bts)
    assert plan is not None, 'sayfa dizisi okunamadı'
    blacks = [i + 1 for i, x in enumerate(plan) if x is None]
    assert blacks == [5, 23, 35, 67, 77, 85], blacks
    assert len(plan) == 113, len(plan)


def test_dvd2_page_numbers():
    """2006+ görsel klasörleri: iki adlandırma kuralı ve tek kapak kuralı."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dvd2-images2pdf.py')
    spec = importlib.util.spec_from_file_location('d2', path)
    d2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d2)

    # 2006-07: tek numaralı dosya TEK sayfa
    assert d2.page_numbers('ocak08_panorama.jpg') == (8, 8)
    assert d2.page_numbers('ocak11_12_panorama.jpg') == (11, 12)
    assert d2.page_numbers('Ocak_22_23_aylayasam.jpg') == (22, 23)
    # 2008+: tek numaralı dosya bir YAY (2 sayfa); yıl eki sayılmaz
    assert d2.page_numbers('004_ocak.jpg', True) == (4, 5)
    assert d2.page_numbers('010_011_ocak.jpg', True) == (10, 11)
    assert d2.page_numbers('006_ocak2011.jpg', True) == (6, 7)
    assert d2.page_numbers('KAPAK_Ocak.jpg') is None

    with tempfile.TemporaryDirectory() as d:
        Image.new('RGB', (80, 107), (10, 10, 10)).save(os.path.join(d, 'KAPAK_ocak.jpg'))
        Image.new('RGB', (160, 214), (20, 20, 20)).save(os.path.join(d, 'AT_202_KAPAK.jpg'))
        Image.new('RGB', (80, 107), (200, 0, 0)).save(os.path.join(d, '002_003_ocak.jpg'))
        cover = os.path.join(d, 'dis_kapak.jpg')
        Image.new('RGB', (80, 107), (0, 0, 200)).save(cover)
        st = d2.build(d, os.path.join(d, 'a.pdf'), pair_single=True, cover=cover)
        assert st['pages'] == 2, st        # 1 kapak + 1 yay — kapak üçlenmemeli


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f'{name}: ok')
    print('hepsi geçti')
