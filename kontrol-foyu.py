#!/usr/bin/env python3
"""Atlas dergi PDF'leri icin 'cift sayfa kontrol foyu' uretir.

Her föy yapragi 6 yay (2 sutun x 3 satir) gosterir; yay = iki komsu sayfa
yan yana. Yanlis eslesmis bir yay (kesilmis foto / kopuk makale) boylece
tek bakista gorulur. Etiketler PDF sayfa numaralaridir ("012-013").

    python3 kontrol-foyu.py                # hepsi
    python3 kontrol-foyu.py <pdf> <pdf>…   # secilmis sayilar
"""
import glob
import math
import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor

import pymupdf
from PIL import Image, ImageDraw

SRC_GLOB = '/Volumes/ebook/dergi/Atlas/*.pdf'
OUTDIR = os.path.expanduser('~/Downloads/Atlas Kontrol')
W_PAGE = 300          # tek sayfa genisligi (px)
COLS, ROWS = 2, 3     # yaprak basina yay sayisi


def render(p, dpi=58):
    pix = p.get_pixmap(dpi=dpi)
    return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def sheet_pdf(src, out):
    doc = pymupdf.open(src)
    imgs = [render(p) for p in doc]
    n = len(imgs)
    if not n:
        return 0

    def sc(im):
        return im.resize((W_PAGE, max(1, round(im.height * W_PAGE / im.width))), Image.LANCZOS)

    thumbs = [sc(im) for im in imgs]
    pairs = [(i, i + 1) for i in range(0, n, 2)]
    cell_w = W_PAGE * 2 + 4
    cell_h = max(t.height for t in thumbs)
    lab, gap, pad = 22, 18, 20
    per = COLS * ROWS
    title = os.path.basename(src).replace('.pdf', '')
    sheets = []
    for s in range(0, len(pairs), per):
        chunk = pairs[s:s + per]
        rows = math.ceil(len(chunk) / COLS)
        canvas = Image.new('RGB', (COLS * (cell_w + gap) + pad,
                                   rows * (cell_h + lab + gap) + 50), 'white')
        d = ImageDraw.Draw(canvas)
        d.text((pad, 16), f'{title}  -  yay {s + 1}-{s + len(chunk)} / {len(pairs)}', fill=(0, 0, 0))
        for k, (a, b) in enumerate(chunk):
            x = pad + (k % COLS) * (cell_w + gap)
            y = 44 + (k // COLS) * (cell_h + lab + gap)
            canvas.paste(thumbs[a], (x, y))
            if b < n:
                canvas.paste(thumbs[b], (x + W_PAGE + 4, y))
            d.text((x + 2, y + cell_h + 4), f'{a + 1:03d}-{b + 1:03d}', fill=(0, 0, 0))
        sheets.append(canvas)
    sheets[0].save(out, save_all=True, append_images=sheets[1:], resolution=150, quality=70)
    return len(sheets)


def one(src):
    name = os.path.basename(src).replace('.pdf', '')
    out = os.path.join(OUTDIR, name + ' - kontrol.pdf')
    if os.path.exists(out):
        return name, -1
    if shutil.disk_usage(OUTDIR).free < 1 << 30:      # disk %99: yer yoksa başlamayalım
        return name, 'ATLANDI: disk dolu'
    try:
        return name, sheet_pdf(src, out)
    except Exception as e:                       # tek sayi patlarsa devam
        return name, f'HATA: {e}'


if __name__ == '__main__':
    os.makedirs(OUTDIR, exist_ok=True)
    files = sys.argv[1:] or sorted(glob.glob(SRC_GLOB))
    with ProcessPoolExecutor(6) as ex:
        for name, res in ex.map(one, files):
            print(f'{name}: {res}', flush=True)
    # ponytail: kendini kontrol eden tek satir — her PDF gercekten yazildi mi
    missing = [f for f in files
               if not os.path.exists(os.path.join(
                   OUTDIR, os.path.basename(f).replace('.pdf', '') + ' - kontrol.pdf'))]
    print('eksik:', len(missing), 'toplam:', len(files))
    assert not missing, missing[:3]
