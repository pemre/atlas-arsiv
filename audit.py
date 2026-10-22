"""Arşiv denetimi: her PDF'in sayfa sayısı bts'nin kendi sayfa dizisiyle uyuşuyor mu?"""
import glob
import os
import sys

sys.path.insert(0, '/Users/user/Downloads/github-pemre/atlas-arsiv')
import pymupdf

import atlas2pdf as A

OUT = '/Volumes/ebook/dergi/Atlas'
files = sorted(glob.glob('/Volumes/ATLAS/DVD1/*/*.bts') + glob.glob('/Volumes/ATLAS 1/DVD2/*/*.bts'))
bad, total_pages, total_blank, no_plan = [], 0, 0, []
for bts in files:
    meta = A.issue_meta(bts)
    year, sayi, issue = meta
    name = f'{year}-{sayi:02d} Atlas Dergisi {issue:03d}'
    pdf = os.path.join(OUT, name + '.pdf')
    plan = A.page_plan(bts)
    if plan is None:
        no_plan.append(name)
        continue
    exp_pages = len(plan)
    exp_blank = plan.count(None)
    if not os.path.exists(pdf):
        bad.append((name, 'PDF YOK', exp_pages, '-'))
        continue
    got = pymupdf.open(pdf).page_count
    total_pages += got
    total_blank += exp_blank
    if got != exp_pages:
        bad.append((name, 'SAYFA FARKI', exp_pages, got))

pdfs = sorted(glob.glob(os.path.join(OUT, '*.pdf')))
print('bts:', len(files), '| PDF:', len(pdfs))
print('toplam sayfa:', total_pages, '| siyah dolgu:', total_blank)
print('dizisi okunamayan:', no_plan)
print('sorunlu:', len(bad))
for b in bad:
    print('  !', b)
