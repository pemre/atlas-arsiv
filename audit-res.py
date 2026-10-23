#!/usr/bin/env python3
"""Arşivdeki PDF'lerde 'baskın çözünürlükten küçük' sayfaları bulur (paralel).

Çıktı: /tmp/kucuk.json — {pdf: {"baskin": [w,h], "kucuk": [[sayfa,[w,h]], ...]}}
Yeniden çalıştırılabilir: bitmiş dosyalar atlanır.
"""
import glob
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pymupdf

CIKTI = '/tmp/kucuk.json'


def bak(f):
    try:
        d = pymupdf.open(f)
        boy = []
        for p in d:
            im = p.get_images(full=True)
            boy.append((im[0][2], im[0][3]) if im else None)
    except Exception as e:
        return f, {'hata': str(e)}
    gecerli = [b for b in boy if b]
    if not gecerli:
        return f, {}
    baskin = Counter(gecerli).most_common(1)[0][0]
    kucuk = [[i + 1, list(b)] for i, b in enumerate(boy)
             if b and b[0] * b[1] < 0.5 * baskin[0] * baskin[1]]
    return f, {'baskin': list(baskin), 'kucuk': kucuk, 'sayfa': len(boy)}


def main():
    veri = json.load(open(CIKTI)) if os.path.exists(CIKTI) else {}
    kalan = [f for f in sorted(glob.glob('/Volumes/ebook/dergi/Atlas/*.pdf')) if f not in veri]
    print(f'{len(kalan)} dosya taranacak', flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f, r in ex.map(bak, kalan):
            veri[f] = r
            json.dump(veri, open(CIKTI, 'w'), ensure_ascii=False)
    print('BİTTİ', len(veri), flush=True)


if __name__ == '__main__':
    main()
