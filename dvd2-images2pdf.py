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


PAGE = re.compile(r'(?:pages?|sayfa)[\s_.\-]*(\d{1,3})(?:[\s_.\-]*(\d{1,3}))?')


def page_numbers(filename):
    """Dosya adından (ilk sayfa, son sayfa) çıkar; yay mı tek sayfa mı sonra belli olur.

    Adlandırma yıldan yıla değişiyor, ikisi de desteklenir:
        01_page012_013.jpg -> 12, 13      004_ocak.jpg -> 4
        ocak04_05panorama.jpg -> 4, 5     Ocak_22_23.jpg -> 22, 23
    """
    s = os.path.splitext(filename)[0].lower()
    for m in MONTHS:
        s = s.replace(m, ' ')
    s = re.sub(r'(19|20)\d{2}', ' ', s)          # yıl eki: ocak2011 -> ocak
    m = PAGE.search(s) or LEAD.match(s)
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    if b != a and b != a + 1:                    # çift değil (başlıktaki sayı)
        b = a
    return (a, b) if a >= 1 else None


def is_spread(path, threshold=1.2):
    """Yay görselleri iki sayfa genişliğinde (oran ~1.5), tek sayfa ~0.76."""
    with Image.open(path) as im:
        w, h = im.size
    return w / h > threshold


def _cekirdek(ad):
    """'Ocak_014_015_L.jpg' -> '014_015' ; '001_s.jpg' -> '001' — ay eki ve
    _L/_s/_2 gibi sürüm ekleri atılır, eşleşme sayı çekirdeği üzerinden yapılır."""
    s = os.path.splitext(ad)[0].lower()
    for m in MONTHS:
        s = s.replace(m, '_')
    s = re.sub(r'[^0-9]+', '_', s)
    return '_'.join(x for x in s.split('_') if x)


def dir_order(folder):
    """2008+: <yıl>/**.dir içindeki sıralı jpg adları = uygulamanın gerçek sayfa sırası.

    Director cast'i görselleri bu sırayla yükler; ad sıralamasından daha güvenilir
    (aynı sayfanın 2/3/4 kopyaları, boşluklu adlar, klasörde olmayan kayıtlar var)."""
    from pathlib import Path
    p = Path(folder).resolve()
    yil = next((x.name for x in p.parents if x.name.isdigit() and len(x.name) == 4), None)
    ay = month_of(p.name)
    if not yil or not ay:
        return None
    kok = next(x for x in p.parents if x.name == yil).parent
    import glob
    from pathlib import Path as P
    d = sorted(glob.glob(os.path.join(kok, yil, '**', f'*{MONTHS[ay - 1]}*.dir'),
                         recursive=True))
    if not d:
        return None
    ham = P(d[0]).read_bytes()
    # ayırıcı (_ ya da -) şart: '2011.jpg' gibi arayüz görselleri sayfa sanılmasın
    adlar = [m.group(0).decode() for m in
             re.finditer(rb'[0-9]{3}[_\-][^\s/:*?"<>|]{0,30}\.jpg', ham, re.I)]
    if adlar:
        sira = list(dict.fromkeys(_cekirdek(a) for a in adlar))    # sıra korunur
    else:
        # 2009-2012: .dir sayfa dosya adlarını taşımıyor, yalnız '004_' gibi
        # numara önekleri var (ad sonrası Türkçe karakterde kesiliyor).
        # Bu önekler cast sırasıyla dizilidir → sıra buradan çıkar.
        sira = []
        for parca in re.split(rb'[^\x20-\x7e]+', ham):
            m = re.match(rb'(\d{3})_', parca)
            if m:
                s = m.group(1).decode()
                if s not in sira:
                    sira.append(s)
        # .dir tek tek basılı sayfayı listeler (040), klasörde yay olarak durur
        # (040_041.jpg) → eşleşme ilk üç rakam üzerinden yapılır.
        isim = {}
        for f in os.listdir(folder):
            if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            m2 = re.match(r'(\d{3})', f)
            if not m2:
                continue
            k, yol = m2.group(1), os.path.join(folder, f)
            if k not in isim or os.path.getsize(yol) > os.path.getsize(
                    os.path.join(folder, isim[k])):
                isim[k] = f
        if not sira or len([a for a in sira if a in isim]) < len(isim) * 0.5:
            return None
        bulunan = [isim[a] for a in sira if a in isim]
        kalan = [f for f in sorted(os.listdir(folder))
                 if f not in set(bulunan) and f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        return bulunan + kalan
    mevcut, hepsi = {}, []
    for f in os.listdir(folder):               # aynı çekirdeğin büyük kopyası seçilir
        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
            hepsi.append(f)
            c = _cekirdek(f)
            if c not in mevcut or os.path.getsize(os.path.join(folder, f)) > \
                    os.path.getsize(os.path.join(folder, mevcut[c])):
                mevcut[c] = f
    bulunan = [mevcut[a] for a in sira if a in mevcut]
    # .dir yarısından azını kapsıyorsa (2008 aralik.dir gibi tek kayıtlı çöp
    # dosyalar) sıraya güvenme, ad sıralamasına dön
    if len(bulunan) < 0.5 * len(mevcut):
        return None
    # aynı çekirdeğe düşen ikizler yüzünden hiç görsel kaybolmasın
    return bulunan + [f for f in sorted(hepsi) if f not in set(bulunan)]


def _ayni(a, b, n=1 << 20):
    """İlk 1 MB aynıysa aynı dosya say (kopya adları ayıklamak için)."""
    try:
        with open(a, 'rb') as fa, open(b, 'rb') as fb:
            return fa.read(n) == fb.read(n)
    except OSError:
        return False


# Altında sayfa numarası olmayan katlanır sayfalar: uygulamada göründükleri aralık.
# (2006-07'de iki katlama, 53-54 yayından sonra, 55-56'dan önce.)
# (sayfa aralığı, aynı aralıktaki sıra) — sıra uygulamanın gösterdiği sıra:
# önce harita (_2), sonra vadinin fotoğrafı (_1).
KAPAK_THUMBS = {'160', '164'}      # 2006: uygulamada kapak var, Images'te yok

KATLAMA_YER = {
    'temmuz_katlama_1_kelkit.jpg': ((54, 55), 1),
    'temmuz_katlama_2_kelkit.jpg': ((54, 55), 0),
}
log_uyari = []


def collect(folder, order=None):
    """({(ilk, son): dosya}, [numarasız kapaklar]) — en büyük dosya seçilir.

    Ad tek sayfa numarası veriyorsa yay olup olmadığına görselin en-boy oranı
    karar verir: adlar yıldan yıla değişiyor, oran değişmiyor."""
    if order:                                  # .dir sırası varsa o kullanılır
        kalan = [f for f in sorted(os.listdir(folder))
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))
                 and f not in set(order)]
        seq = [f for f in list(order) + kalan
               if os.path.exists(os.path.join(folder, f))]      # hayalet kayıt
        kesin = {(i + 1, i + 1): [os.path.join(folder, f)] for i, f in enumerate(seq)}
        return kesin, []

    best = {}
    prepend = []
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        path = os.path.join(folder, f)
        if not os.path.exists(path):          # ISO'da boş klasör kaydı olabilir
            continue
        pn = page_numbers(f)
        # kapak: yalnız ön kapak başa alınır (numarasız ya da 1. sayfa).
        # Arka kapak (ör. ekim_109_kapak.jpg) kendi sayfa numarasında kalır —
        # hepsini başa almak arka kapağı 2. sayfaya taşıyordu.
        if 'kapak' in f.lower() or 'cover' in f.lower():
            if pn is None or pn[0] <= 1:
                prepend.append(path)
                continue
            a, b = pn
            best.setdefault((a, b), []).append(path)
            continue
        if not pn:
            # katlanır sayfa (ör. temmuz_katlama_1_kelkit.jpg) numara taşımıyor;
            # uygulamada 53-54 yayından sonra görünüyor → o aralığa yerleştirilir
            if 'katlama' in f.lower():
                yer = KATLAMA_YER.get(f)
                if yer is None:
                    log_uyari.append(f)
                    yer = ((999, 999), 0)
                anahtar, sira = yer
                best.setdefault(anahtar, []).insert(sira, path)
            continue
        a, b = pn
        if b == a and is_spread(path):         # tek numara ama görsel yay
            pn = (a, a + 1)
        # aynı sayfa anahtarına düşen dosyalar farklı içerik olabilir
        # (2006-01'de ocak08._panorama.jpg ile ocak08_panorama.jpg iki ayrı sayfa);
        # yalnız BİREBİR aynı dosya atılır, gerisi ad sırasıyla korunur
        liste = best.setdefault(pn, [])
        if any(os.path.getsize(path) == os.path.getsize(x) and _ayni(path, x) for x in liste):
            continue
        liste.append(path)
    _yay_tekrarini_at(best)
    return best, prepend


def _vektor(x, n=24):
    """Görüntü (yol ya da Image) → 24×24 gri, ortalaması çıkarılmış vektör."""
    from PIL import Image
    im = Image.open(x) if isinstance(x, str) else x
    g = im.convert('L').resize((n, n), Image.LANCZOS)
    d = [int(p) - 128 for p in g.getdata()]
    m = sum(d) / len(d)
    return [p - m for p in d]


def _benzer(a, b, n=24):
    """İki görüntünün 24×24 gri vektörleri arasındaki kosinüs benzerliği."""
    v = [_vektor(a, n), _vektor(b, n)]
    pay = sum(x * y for x, y in zip(*v))
    payda = (sum(x * x for x in v[0]) ** .5) * (sum(y * y for y in v[1]) ** .5)
    return pay / payda if payda else 0.0


def _yay_tekrarini_at(best):
    """Tek sayfa, aynı numaradan başlayan yayın sol yarısıysa tek sayfa atılır.

    2007-02: `02_page082.jpg` görsel olarak `02_page082_083.jpg`'nin sol yarısı
    (benzerlik 0.99); uygulama yalnız yayı gösteriyor — ikisi birden PDF'e
    girince aynı sayfa iki kez basılıyordu. 2006+2007'de tek örnek bu."""
    from PIL import Image
    for (a, b), liste in list(best.items()):
        if a != b or not liste or not best.get((a, a + 1)):
            continue
        yay = best[(a, a + 1)][0]
        try:
            im = Image.open(yay); w, h = im.size
            sol = im.crop((0, 0, w // 2, h)).copy(); im.close()
        except OSError:
            continue
        kalan = []
        for tek in liste:
            try:
                if _benzer(tek, sol) > 0.85:
                    log_uyari.append(f'yay tekrari atildi: {os.path.basename(tek)}')
                    continue
            except OSError:
                pass
            kalan.append(tek)
        if kalan:
            best[(a, b)] = kalan
        else:
            del best[(a, b)]


def thumbs_cover(folder):
    """Kapak yalnız Thumbs/<no>/ içinde kalmışsa onu kullan (517×690, bulanık).

    2006-07'de bazı sayıların kapağı Images/ klasöründe yok; uygulama yine de
    kapak gösteriyor (kaynak: Thumbs)."""
    dergi = os.path.dirname(os.path.dirname(folder))      # .../Dergi/Images/<no>
    d = os.path.join(dergi, 'Thumbs', os.path.basename(folder))
    if not os.path.isdir(d):
        return None
    for f in sorted(os.listdir(d)):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')) and 'kapak' in f.lower():
            return os.path.join(d, f)
    return None


def build(folder, pdf_path, log=print, cover=None, blanks=False):
    picks, prepend = collect(folder, dir_order(folder))
    prepend = [max(prepend, key=os.path.getsize)] if prepend else []   # tek kapak
    # Uygulama bu sayılarda ayrıca bir kapak gösteriyor ama Images'te kapak
    # dosyası yok (yalnız Thumbs'ta 517×690 var). Diğerlerinde ilk sayfa zaten
    # kapağın kendisi; oraya kapak eklemek sayfayı yineliyor.
    if not prepend and os.path.basename(folder) in KAPAK_THUMBS:
        k = thumbs_cover(folder)
        if k:
            prepend = [k]
    cover = None if prepend else cover        # klasörde kapak varsa dışarıkini alma
    if cover and not any(a <= 1 <= b for a, b in picks):
        picks.setdefault((1, 1), []).append(cover)    # kapak ayrı klasörde
    if not picks:
        raise ValueError('sayfa görseli bulunamadı: ' + folder)
    keys = sorted(picks)
    maxpage = keys[-1][1]
    covered = {p for a, b in keys for p in range(a, b + 1)}
    gaps = sorted(set(range(1, maxpage + 1)) - covered)

    # Her görsel SIRAYLA bir kez girer. Aralıklar çakışabilir (ör. 010 hem
    # "010_011" yayı hem tek sayfa olarak bulunabiliyor); sayfa tarayarak
    # eşleştirmek çakışan görselleri sessizce düşürüyordu.
    files, blanked, prev, size = list(prepend), 0, 1 if prepend else 0, None
    for a, b in keys:
        if blanks and files and a > prev + 1:
            files.extend([None] * (a - prev - 1))    # delik -> siyah (opt-in)
            blanked += a - prev - 1
        for path in picks[(a, b)]:
            if size is None:
                size = Image.open(path).size
            files.append(path)
        prev = max(prev, b)
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
    n_gorsel = sum(len(v) for v in picks.values())
    log(f'  {n_gorsel} görsel -> {len(files)} sayfa ({blanked} dolgu), '
        f'{os.path.getsize(pdf_path) / 1e6:.1f} MB')
    return dict(images=n_gorsel, pages=len(files), blanks=blanked, gaps=gaps)


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
    ap.add_argument('--blanks', action='store_true',
                    help='numara atlamalarına siyah dolgu koy (varsayılan: koyma; '
                         '2006+ DVD taramaları delikli, dolgu uydurma olur)')
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
                  cover=find_cover(args.root, args.year, month),
                  blanks=args.blanks)
        except Exception as e:
            print(f'  HATA: {e}')


if __name__ == '__main__':
    main()
