#!/usr/bin/env python3
"""Atlas DVD2 (2006+) sayfa görsellerinden PDF üretir.

2006'dan sonra içerik Flash değil: her ayın sayfaları ayrı JPG dosyaları.
Sayfa SIRASI dosya adlarının içindeki numaralarda yazılı:

    ocak04_05panorama.jpg   -> 4-5 yayı (tek geniş görsel)
    ocak13_atlas raporu.jpg -> 13. sayfa
    006_ocak2011.jpg        -> 6. sayfa

Yay görselleri ikiye BÖLÜNMEZ (fotoğraf kesilmesin), tek geniş sayfa olarak girer.
Nunarada atlanan yer varsa (DVD'ye konmamış sayfa) siyah dolgu eklenir.

    python3 dvd2-images2pdf.py --year 2006 --out ~/AtlasPDF
"""
import argparse
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas2pdf as A

MONTHS = ['ocak', 'subat', 'mart', 'nisan', 'mayis', 'haziran',
          'temmuz', 'agustos', 'eylul', 'ekim', 'kasim', 'aralik']
LEAD = re.compile(r'^[\s_.\-]*(\d{1,3})(?:[\s_.\-]*(\d{1,3}))?')


def page_numbers(filename, pair_single=False):
    """Dosya adından (ilk sayfa, son sayfa) çıkar.

    pair_single=True: tek numaralı ad da bir YAY (2 sayfa). 2008'den sonraki
    klasörlerde her dosya basılı derginin bir yayıdır (sol sayfa numarası yazılı)."""
    s = os.path.splitext(filename)[0].lower()
    for m in MONTHS:
        s = s.replace(m, ' ')
    s = re.sub(r'(19|20)\d{2}', ' ', s)          # yıl eki: ocak2011 -> ocak
    m = LEAD.match(s)
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    if b != a and b != a + 1:                    # sayı çifti değil (başlıktaki sayı)
        b = a
    if pair_single and b == a:
        b = a + 1                                # tek numara = yay
    return (a, b) if a >= 1 else None


def collect(folder, pair_single=False):
    """({(ilk, son): dosya}, [numarasız kapaklar]) — en büyük dosya seçilir."""
    best = {}
    prepend = []
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        pn = page_numbers(f, pair_single)
        if not pn:
            if 'kapak' in f.lower() or 'cover' in f.lower():
                prepend.append(os.path.join(folder, f))   # numarasız kapak
            continue
        path = os.path.join(folder, f)
        if not os.path.exists(path):          # ISO'da boş klasör kaydı olabilir
            continue
        if pn not in best or os.path.getsize(path) > os.path.getsize(best[pn]):
            best[pn] = path
    return best, prepend


def build(folder, pdf_path, log=print, pair_single=False, cover=None):
    picks, prepend = collect(folder, pair_single)
    prepend = [max(prepend, key=os.path.getsize)] if prepend else []   # tek kapak
    cover = None if prepend else cover        # klasörde kapak varsa dışarıkini alma
    if cover and not any(a <= 1 <= b for a, b in picks):
        picks[(1, 1)] = cover                 # kapak ayrı klasörde
    if not picks:
        raise ValueError('sayfa görseli bulunamadı: ' + folder)
    keys = sorted(picks)
    maxpage = keys[-1][1]
    covered = {p for a, b in keys for p in range(a, b + 1)}
    gaps = sorted(set(range(1, maxpage + 1)) - covered)

    seq, size = [], None
    for p in range(1, maxpage + 1):
        hit = next(((a, b) for a, b in keys if a <= p <= b), None)
        if hit is None or hit[0] != p:           # yayın ikinci yarısı: zaten eklendi
            if hit is None:
                seq.append(None)                 # eksik sayfa -> siyah
            continue
        seq.append(picks[hit])
    # baştaki eksikleri at
    while seq and seq[0] is None:
        seq.pop(0)

    files, blanked = list(prepend), 0
    for item in seq:
        if item is None:
            if files or blanked:
                files.append(None)
                blanked += 1
            continue
        size = Image.open(item).size
        files.append(item)
    if blanked:
        tmp = pdf_path + '.d'
        os.makedirs(tmp, exist_ok=True)
        out = []
        for i, f in enumerate(files):
            if f is None:
                path = os.path.join(tmp, f'b{i:04d}.jpg')
                Image.new('RGB', size or (800, 1067), (0, 0, 0)).save(path, quality=80)
                out.append(path)
            else:
                out.append(f)
        files = out
    A.write_pdf(files, pdf_path)
    log(f'  {len(picks)} görsel -> {len(files)} sayfa ({blanked} dolgu), '
        f'{os.path.getsize(pdf_path) / 1e6:.1f} MB')
    return dict(images=len(picks), pages=len(files), blanks=blanked, gaps=gaps)


def month_of(folder_name):
    """'01_Ocak' / '01 Ocak' / 'agustos_1500' -> 1..12"""
    low = folder_name.lower()
    for i, m in enumerate(MONTHS, 1):
        if m in low:
            return i
    return None


def list_2006_2007(root, year):
    """<yıl>/Dergi/Images/<sayı no>/ — klasör adı derginin sayı numarası."""
    base = os.path.join(root, str(year), 'Dergi', 'Images')
    out = []
    for n in sorted(os.listdir(base)):
        d = os.path.join(base, n)
        if n.isdigit() and os.path.isdir(d):
            out.append((int(n), month_of('') or 0, d))
    return out


def list_by_month(root, year, pattern):
    """Ay klasörleri: images/large/01_Ocak gibi. pattern = alt klasör adı."""
    base = os.path.join(root, str(year), pattern)
    out = []
    if not os.path.isdir(base):
        return out
    for n in sorted(os.listdir(base)):
        d = os.path.join(base, n)
        m = month_of(n)
        if os.path.isdir(d) and m:
            out.append((None, m, d))
    return out


def list_2008(root, year):
    """content/aylar/<ay>_1000 ve _1500 — yüksek çözünürlüklü olanı seç."""
    base = os.path.join(root, str(year), 'content', 'aylar')
    pick = {}
    for n in sorted(os.listdir(base)):
        m = month_of(n)
        if m and os.path.isdir(os.path.join(base, n)):
            if m not in pick or '1500' in n:
                pick[m] = os.path.join(base, n)
    return [(None, m, pick[m]) for m in sorted(pick)]


def find_cover(root, year, month):
    """Kapak (sayfa 1) sayfa klasörünün dışında tutuluyor: images/kapaklar/…"""
    base = os.path.join(root, str(year), 'images')
    for sub in ('kapaklar', 'kapaklar_2', '_kapaklar'):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            if month_of(f) != month:
                continue
            if page_numbers(f) in (None, (1, 1), (1, 2)):
                return os.path.join(d, f)
        hits = [f for f in sorted(os.listdir(d)) if month_of(f) == month]
        if hits:
            return os.path.join(d, hits[0])
    return None


def list_issues(root, year):
    if year in (2006, 2007):
        return list_2006_2007(root, year)
    if year == 2008:
        return list_2008(root, year)
    if year in (2009, 2010):
        return list_by_month(root, year, os.path.join('images', 'large'))
    if year == 2011:
        return list_by_month(root, year, os.path.join('images', 'large_2'))
    if year == 2012:
        return list_by_month(root, year, os.path.join('images', '_Large'))
    return []


def month_2006_2007(year, issue):
    """2006-01 = 154: sayı numarasından ay."""
    return (issue - 154) % 12 + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/Volumes/ATLAS 1/DVD2')
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--out', default=os.path.expanduser('~/AtlasPDF'))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    items = list_issues(args.root, args.year)
    if not items:
        sys.exit(f'{args.year} için sayfa klasörü bulunamadı')

    for issue, month, folder in items:
        if issue is None:                       # aya göre düzenlenmiş yıllar
            issue = 154 + (args.year - 2006) * 12 + (month - 1)
        elif not month:
            month = month_2006_2007(args.year, issue)
        name = f'{args.year}-{month:02d} Atlas Dergisi {issue:03d}'
        print(f'{name}:', flush=True)
        try:
            build(folder, os.path.join(args.out, name + '.pdf'),
                  pair_single=args.year >= 2008,
                  cover=find_cover(args.root, args.year, month))
        except Exception as e:
            print(f'  HATA: {e}')


if __name__ == '__main__':
    main()
