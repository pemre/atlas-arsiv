#!/usr/bin/env python3
"""Atlas Dergisi arşivi: SWF/.bts dosyalarını doğru sayfa sırasıyla JPG + PDF'e çevirir.

Tek dosya:
    python3 atlas2pdf.py sayi4.swf sayi4_pages
    python3 atlas2pdf.py sayi4.swf sayi4_pages --blanks 4,21,32,63,72,79
    python3 atlas2pdf.py sayi4.swf sayi4_pages --tiles 102-107 --pdf-only

Bütün DVD (bağlı ISO ya da klasör):
    python3 atlas2pdf.py --batch /Volumes/ATLAS/DVD1 --out ~/AtlasPDF
    python3 atlas2pdf.py --batch /Volumes/ATLAS-1/DVD2 --out ~/AtlasPDF

Sayfa sırası nereden geliyor?
    SWF'te her sayfa için bir sprite vardır ve EXPORTASSETS etiketinde adı "p1".."pNNN"
    olarak yazılıdır. Adlar dosyada ALFABETİK durur (p1, p10, p100, ...); ada göre
    sıralayan her araç sayfa sırasını bozar. Doğrusu addaki sayıya göre sıralamak.
    Zincir:  "pN" -> sprite -> PLACEOBJECT2 çocuğu -> DefineShape -> bitmap fill id
"""
import hashlib
import os
import re
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import zlib
from collections import defaultdict

from PIL import Image, ImageChops

IMGC = (6, 20, 21, 35, 36, 90)   # DefineBits, Lossless, JPEG2/3/4, Lossless2

# Elle doğrulanmış siyah dolgu konumları: {sayı no: (bu sayfalardan SONRA dolgu)}
# 1. sayı (Nisan 1993) basılı dergide CD'ye aktarılmayan reklam sayfaları yüzünden
# çift sayfa görünümünde kayıyordu; konumlar basılı dergiyle karşılaştırılarak bulundu.
# Artık gerekmiyor: dolgu yerleri bts'nin kendi ActionScript sayfa dizisinde "dummy"
# olarak yazılı (bkz. page_plan). Bu sözlük yalnız elle geri düşüş için.
# pageMask'in sonuna YAZILMAYAN ama uygulamanın son sayfa olarak gösterdiği sayfalar.
# Elle doğrulandı (1993-10/007: dizi p117+dummy ile bitiyor, uygulamanın son sayfası
# p118 "özel ilan sayfaları"). Otomatik kural denendi: 6 sayıda aynı desen çıktı ama
# 2002-02'deki aday sayfa dizinin son sayfasının kopyasıydı → kural değil, liste.
# Dizide olan ama basılmayan/tekrar eden sayfalar (elle doğrulandı).
# 1994-02: p112-p114 düşük çözünürlüklü ikiz ailesinde, içerikleri p110-p112 ile aynı
# → PDF'te 114-116. sayfaların aynısı olarak tekrar ediyorlardı.
ATLA = {11: ('p112', 'p113', 'p114')}

SON_EK = {7: 'p118',        # 1993-10: "özel ilan sayfaları" (uygulamada görüldü)
          107: 'p145',      # 2002-02: "mektup" sayfası (folyo 139) — içerik farklı
          137: 'p225'}      # 2004-08: "Bin Yılın Türkleri" (folyo 190) — içerik farklı

BLANKS = {1: (4, 21, 32, 63, 72, 79),
          2: (34, 77, 84)}   # siyah, bildirilen sayfanın KENDİSİ olur (35, 78, 85)


def page_plan(swf):
    """Derginin KENDİ sayfa dizisi: [sembol_adı ... None(dummy/boş sayfa) ...].

    Flash uygulaması (setPages) diziyi push ederken ters yazar, InitArray çevirir.
    dummy = basılı dergide olup DVD'ye aktarılmayan sayfa; oraya siyah dolgu girer.
    Sembol adları pN (sayfa) ya da preklamN (reklam sayfası) olabilir.
    Sondaki dummy (arka kapak) atlanır — PDF'i iki sayfa eksik bırakmasın.
    """
    out = subprocess.run(['swfdump', '-a', swf], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if '("Array")' not in line or '"pageMask"' not in line:
            continue
        names = re.findall(r'\((?:"([^"]*)"|-?\d+)\)', line)[1:]
        if names and names[-1] == 'Array':
            names = names[:-1]
        seq = [s for s in reversed(names)
               if s == 'dummy' or re.fullmatch(r'[a-z_]+\d+_*', s)]
        if not seq:
            continue
        while seq and seq[-1] == 'dummy':        # sondaki dummy = arka kapak
            seq.pop()
        # Aynı sayfanın varyantları arasındaki dummy (p55___ , dummy , p55____) basılı
        # dergide boşluk değil, katlama kırımı → atılır. Gerçek eksik sayfalar kalır.
        out_seq = []
        for i, s in enumerate(seq):
            v = None if s == 'dummy' else s
            if v is None:
                if out_seq and out_seq[-1] is None:
                    continue
                onceki = out_seq[-1] if out_seq else None
                sonraki = next((x for x in seq[i + 1:] if x != 'dummy'), None)
                mp = re.fullmatch(r'p(\d+)_*', onceki or '')
                mn = re.fullmatch(r'p(\d+)_*', sonraki or '')
                if mp and mn and mp.group(1) == mn.group(1):
                    continue
            out_seq.append(v)
        return out_seq
    return None


# ---------------------------------------------------------------- swf okuma
def load(path):
    d = open(path, 'rb').read()
    if d[:3] == b'CWS':
        body = zlib.decompress(d[8:])
    elif d[:3] == b'FWS':
        body = d[8:]
    elif d[:3] == b'ZWS':
        import lzma
        body = lzma.decompress(d[12:])
    else:
        raise ValueError('SWF değil: ' + path)
    nbits = body[0] >> 3
    return body, (5 + 4 * nbits + 7) // 8 + 4


def walk(body, pos, end=None):
    """Bütün tag'ler, DefineSprite içlerine inerek."""
    end = len(body) if end is None else end
    while pos + 2 <= end:
        rc = struct.unpack('<H', body[pos:pos + 2])[0]
        pos += 2
        code, ln = rc >> 6, rc & 0x3f
        if ln == 0x3f:
            ln = struct.unpack('<I', body[pos:pos + 4])[0]
            pos += 4
        yield code, pos, ln
        if code == 39:
            yield from walk(body, pos + 4, pos + ln)
        pos += ln


def read_swf(swf):
    body, pos = load(swf)
    images, sprites, exports = {}, {}, {}
    for code, p, ln in walk(body, pos):
        if code in IMGC:
            images[struct.unpack('<H', body[p:p + 2])[0]] = code
        elif code == 39:                                   # DefineSprite
            sid = struct.unpack('<H', body[p:p + 2])[0]
            kids = []
            for c2, pp, l2 in walk(body, p + 4, p + ln):
                if c2 == 26 and (body[pp] & 0x02):         # PlaceObject2 + karakter
                    kids.append(struct.unpack('<H', body[pp + 3:pp + 5])[0])
            sprites[sid] = kids
        elif code == 56:                                   # ExportAssets
            cnt = struct.unpack('<H', body[p:p + 2])[0]
            i = p + 2
            for _ in range(cnt):
                cid = struct.unpack('<H', body[i:i + 2])[0]
                i += 2
                e = body.index(b'\0', i)
                exports[body[i:e].decode('utf8', 'replace')] = cid
                i = e + 1
    return images, sprites, exports


def shape_bitmaps(swf):
    """swfdump -u çıktısından shape id -> kullandığı bitmap id'leri (ondalık)."""
    out = subprocess.run(['swfdump', '-u', swf], capture_output=True, text=True).stdout
    uses, cur = {}, None
    for line in out.splitlines():
        if re.match(r'^\[[0-9a-f]{3}\]', line):
            m = re.search(r'DEFINESHAPE\w* defines id (\d+)', line)
            cur = int(m.group(1)) if m else None
            continue
        m = re.search(r'uses IDs: (.*)', line)
        if m and cur is not None:
            uses[cur] = [int(x.rstrip(',')) for x in m.group(1).split() if x.rstrip(',')]
            cur = None
    return uses


def first_bitmap(sid, sprites, uses, images, depth=0):
    for c in sprites.get(sid, []):
        if c in uses:
            # Shape'in bitmap listesinde alfa taşıyan JPEG3 (ör. kapak üstündeki logo)
            # önce gelirse sayfa sanılıyor ve swfextract JPEG2'yi bulamayınca o sayfa
            # düşük çözünürlüklü ikizine düşüyor. Önce alfasız JPEG2 (tag 21) denenir.
            for u in sorted(uses[c], key=lambda u: 0 if images.get(u) == 21 else 1):
                if u in images:
                    return u
        elif c in sprites and depth < 5:
            r = first_bitmap(c, sprites, uses, images, depth + 1)
            if r:
                return r
    return None


def page_images(swf):
    """Sayfa sırasına göre bitmap id listesi (en yüksek çözünürlüklü aile)."""
    images, sprites, exports = read_swf(swf)
    uses = shape_bitmaps(swf)
    fams = defaultdict(dict)
    for name, sid in exports.items():
        m = re.fullmatch(r'([a-zA-Z_]*?)(\d+)(_*)', name)
        if m:
            img = first_bitmap(sid, sprites, uses, images)
            if img:
                fams[m.group(1)][(int(m.group(2)), m.group(3))] = img
    if not fams:
        raise ValueError('sayfa etiketi (pN) bulunamadı')
    return images, sprites, exports, fams


# ---------------------------------------------------------------- pdf
def write_pdf(jpgs, pdf_path):
    """JPEG'leri yeniden sıkıştırmadan gömer (DCTDecode) — sıkıştırılmış veri aynen korunur."""
    out = bytearray(b'%PDF-1.4\n')
    off, kids = {}, []

    def add(num, body):
        off[num] = len(out)
        out.extend(f'{num} 0 obj\n'.encode() + body + b'\nendobj\n')

    for i, f in enumerate(jpgs):
        im = Image.open(f)
        w, h = im.size
        cs = '/DeviceGray' if im.mode == 'L' else '/DeviceRGB'
        data = open(f, 'rb').read()
        img, page, cont = 3 + i * 3, 4 + i * 3, 5 + i * 3
        add(img, (f'<< /Type /XObject /Subtype /Image /Width {w} /Height {h} '
                  f'/ColorSpace {cs} /BitsPerComponent 8 /Filter /DCTDecode '
                  f'/Length {len(data)} >>\nstream\n').encode() + data + b'\nendstream')
        add(page, (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] '
                   f'/Contents {cont} 0 R /Resources << /XObject << /Im0 {img} 0 R >> >> >>').encode())
        s = f'q {w} 0 0 {h} 0 0 cm /Im0 Do Q'.encode()
        add(cont, b'<< /Length %d >>\nstream\n' % len(s) + s + b'\nendstream')
        kids.append(page)
    add(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    add(2, ('<< /Type /Pages /Count %d /Kids [%s] >>'
            % (len(kids), ' '.join(f'{k} 0 R' for k in kids))).encode())
    xref = len(out)
    total = 3 + len(jpgs) * 3
    out.extend(f'xref\n0 {total}\n'.encode() + b'0000000000 65535 f \n')
    for num in range(1, total):
        out.extend(f'{off[num]:010d} 00000 n \n'.encode())
    out.extend(f'trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    open(pdf_path, 'wb').write(out)


# ---------------------------------------------------------------- harita posteri
def black_bars(im, frac=0.9):
    """(sol, sağ, kırpma kutusu, üst, alt) siyah bar kalınlıkları."""
    w, h = im.size
    px = im.load()

    def dark_col(x):
        return sum(1 for y in range(0, h, 3) if sum(px[x, y]) < 45) / (h / 3)

    def dark_row(y):
        return sum(1 for x in range(0, w, 3) if sum(px[x, y]) < 45) / (w / 3)
    l = 0
    while l < w and dark_col(l) > frac:
        l += 1
    r = w - 1
    while r > 0 and dark_col(r) > frac:
        r -= 1
    t = 0
    while t < h and dark_row(t) > frac:
        t += 1
    b = 0
    while b < h and dark_row(h - 1 - b) > frac:
        b += 1
    return l, w - 1 - r, (l, 0, r + 1, h), t, b


def _thumb(im, w=120):
    h = max(1, round(im.height * w / im.width))
    return list(im.convert('L').resize((w, h), Image.BILINEAR).tobytes()), w, h


def _overlap(A, B):
    ga, aw, ah = _thumb(A)
    gb, bw, bh = _thumb(B)
    best = (1e9, 0.0, 0)
    for pct in range(0, 56, 2):
        o = int(bw * pct / 100)
        if o < 6:
            continue
        for dy in (-3, -2, -1, 0, 1, 2, 3):
            s = n = 0
            for y in range(0, min(ah, bh - abs(dy))):
                ya = y + dy
                if ya < 0 or ya >= ah:
                    continue
                ba, bb = ya * aw + aw - o, y * bw
                for x in range(o):
                    s += abs(ga[ba + x] - gb[bb + x])
                    n += 1
            sc = s / max(1, n)
            if sc < best[0]:
                best = (sc, pct / 100, dy)
    return best


def stitch(tiles):
    """Dilimleri soldan sağa, örtüşmeyi bulup kenarları eriterek birleştirir."""
    out = tiles[0].copy()
    for B in tiles[1:]:
        _, frac, dy = _overlap(out, B)
        o = int(B.width * frac)
        dyp = round(dy * B.width / 120)
        canvas = Image.new('RGB', (out.width + B.width - o, max(out.height, B.height + dyp)))
        canvas.paste(out, (0, 0))
        if o > 8:
            mask = Image.new('L', (B.width, B.height), 255)
            mask.paste(Image.linear_gradient('L').rotate(90).resize((o, B.height)), (0, 0))
            canvas.paste(B, (out.width - o, max(0, dyp)), mask)
        else:
            canvas.paste(B, (out.width, max(0, dyp)))
        out = canvas
    return out


def make_poster(pages, out_path, tiles_range=None):
    """Kenarında siyah bar olan ardışık sayfa grubunu (interaktif harita) birleştirir."""
    cand = []
    for i, f in enumerate(pages):
        if tiles_range and not (tiles_range[0] <= i + 1 <= tiles_range[1]):
            continue
        im = Image.open(f).convert('RGB')
        if im.getextrema() == ((0, 0), (0, 0), (0, 0)):
            continue
        if tiles_range:
            cand.append((i, im))
            continue
        small = im.resize((400, round(im.height * 400 / im.width)))
        l, r, _, top, bot = black_bars(small)
        col = small.resize((80, 107))
        raw = col.tobytes()
        sat = sum(max(raw[i:i + 3]) - min(raw[i:i + 3])
                  for i in range(0, len(raw), 3)) / (80 * 107)
        # ponytail: doygunluk eşiği bu dergi ailesine göre kalibre edildi (harita
        # illüstrasyonu renkli, siyah barlı fotoğraf kolajları renksiz). Tutmazsa
        # --tiles ilk-son ile açıkça ver.
        if (l > 10 and r > 10 and sat > 43 and
                top < 0.06 * small.height and bot < 0.06 * small.height):
            cand.append((i, im))
    runs, cur = [], []
    for i, im in cand:
        if cur and i == cur[-1][0] + 1:
            cur.append((i, im))
        else:
            if len(cur) >= 3:
                runs.append(cur)
            cur = [(i, im)]
    if len(cur) >= 3:
        runs.append(cur)
    if not runs:
        return None
    run = max(runs, key=len)
    tiles = [im.crop(black_bars(im)[2]) for _, im in run]
    poster = stitch(tiles)
    poster.save(out_path, quality=92)
    return len(tiles), [i + 1 for i, _ in run], poster.size


def _usable(path):
    """Görsel gerçekten açılabiliyor mu? (bozuk JPEG başlığı olan sayfalar var)"""
    try:
        Image.open(path).size
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- dönüştürme
def convert(swf, out, blanks=(), pdf_only=False, tiles_range=None, name=None, log=print,
            auto_plan=True, son_ek=(), atla=()):
    """Tek bir SWF/.bts dosyasını <out>/NNN.jpg + <out>/<ad>.pdf olarak çıkarır.
    name verilirse PDF/poster bu adı taşır (toplu çevirimde dergi sayı adı)."""
    stem = name or os.path.basename(out)
    tmp = out + '.raw'
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    images, sprites, exports, fams = page_images(swf)
    log(f'  {len(images)} görsel, {len(sprites)} sprite, {len(exports)} export')

    def extract(cid):
        for opt, ext in (('-j', 'jpg'), ('-p', 'png')):
            dst = f'{tmp}/{cid:05d}.{ext}'
            r = subprocess.run(['swfextract', opt, str(cid), swf, '-o', dst], capture_output=True)
            if (r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst)
                    and _usable(dst)):
                return dst
        return None

    areas_of = {}
    for pre, m in fams.items():
        areas = []
        for cid in sorted(m.values())[:8]:
            try:
                w, h = Image.open(extract(cid)).size
                areas.append(w * h)
            except Exception:
                pass
        if areas:
            a = statistics.median(areas)
            areas_of[pre] = a
            if len(m) >= 5:
                log(f'  aile "{pre}N": {len(m)} etiket, medyan {int(a)} px')

    # Sayfa aileleri: en çok etiketli ailenin %90'ı kadar etiketi olanlar (yüksek ve
    # düşük çözünürlüklü ikizler). Küçük kümeler (poster/harita dilimi: "pek", "pa"…)
    # elenir. Sayfa kümesi = aday ailelerin anahtar birleşimi; her sayfa için en yüksek
    # çözünürlüklü kullanılabilir kopya seçilir.
    counts = {pre: len(m) for pre, m in fams.items()}
    top = max(counts.values())
    cands = sorted([pre for pre, c in counts.items() if c >= 0.9 * top],
                   key=lambda pre: -areas_of.get(pre, 0))
    if not cands:
        raise ValueError('sayfa etiketi (pN) bulunamadı')
    keys = sorted(fams[max([pre for pre, c in counts.items() if c == top],
                           key=lambda pre: areas_of.get(pre, 0))])
    blanks = set(blanks)
    log(f'  sayfa ailesi: {", ".join(cands)} — {len(keys)} sayfa')

    # sembol adı ("p36", "preklam1") -> (aile, anahtar); reklam sayfaları ayrı aile
    by_name = {}
    for pre in sorted(fams, key=lambda p: -areas_of.get(p, 0)):
        for k in fams[pre]:
            by_name[pre + str(k[0]) + k[1]] = (pre, k)

    plan = page_plan(swf) if auto_plan else None
    if plan:
        log(f'  sayfa dizisi: bts\'nin kendi sırası, {plan.count(None)} siyah dolgu')
        seq = plan
    else:                                   # geri düşüş: pN sırası + elle dolgular
        own = max([pre for pre, c in counts.items() if c == top],
                  key=lambda pre: areas_of.get(pre, 0))
        seq = []
        for idx, key in enumerate(keys, 1):
            seq.append(own + str(key[0]) + key[1])
            if idx in blanks:
                seq.append(None)

    if atla:                                # elle doğrulanmış atlanacak sayfalar
        oncesi = len(seq)
        seq = [x for x in seq if x not in set(atla)]
        log(f'  atlanan sayfa: {", ".join(atla)} ({oncesi - len(seq)} kayıt)')

    if son_ek:                              # elle doğrulanmış ek son sayfa(lar)
        seq = list(seq) + list(son_ek)
        log(f'  ek son sayfa: {", ".join(son_ek)}')

    pages, n, blanked, size = [], 0, 0, None
    for item in seq:
        if item is None:                    # basılı dergideki eksik sayfa
            if size is None:
                continue
            blanked += 1
            b = f'{tmp}/b{blanked:04d}.jpg'
            Image.new('RGB', size, (0, 0, 0)).save(b, quality=80)
            pages.append(b)
            continue
        hit = by_name.get(item)
        if hit is None:                    # eksik export: aynı numaranın ikizi
            m = re.fullmatch(r'([a-zA-Z_]*?)(\d+)(_*)', item)
            twin = [(p, (int(m.group(2)), m.group(3))) for p in cands
                    if m and (int(m.group(2)), m.group(3)) in fams[p]]
            if twin:
                hit = twin[0]
                log(f'  uyarı: "{item}" yok, "{twin[0][0]}{m.group(2)}" kullanıldı')
        if hit is None:
            log(f'  uyarı: sayfa dizisindeki "{item}" bu dosyada yok')
            continue
        own, key = hit
        f = None
        for pre in [own] + [c for c in cands if c != own]:
            if key in fams[pre]:
                f = extract(fams[pre][key])
                if f:
                    if pre != own:
                        log(f'  uyarı: "{item}" kendi ailesinden çıkarılamadı, '
                            f'"{pre}" kullanıldı')
                    break
        if not f:
            log(f'  atlandı (çıkarılamadı): {item}')
            continue
        # Aynı sayfa iki kez: düşük çözünürlüklü ikiz, önceki sayfanın birebir kopyası
        # olabiliyor (1994-02'de p112-114 = p110-111'in ikizi). Kopya sayfa atılır.
        n += 1
        dst = f'{tmp}/p{n:04d}.jpg'
        shutil.copy(f, dst)
        size = Image.open(f).size
        pages.append(dst)

    final = []
    for i, src in enumerate(pages, 1):
        dst = f'{out}/{i:03d}.jpg'
        shutil.move(src, dst)
        final.append(dst)

    pdf_path = os.path.join(out, stem + '.pdf')
    write_pdf(final, pdf_path)
    log(f'  {len(final)} sayfa ({blanked} siyah dolgu) -> {pdf_path} '
        f'({os.path.getsize(pdf_path) / 1e6:.1f} MB)')

    poster_name = 'harita-poster.jpg' if name is None else name + ' harita-poster.jpg'
    poster = make_poster(final, os.path.join(out, poster_name), tiles_range)
    if poster:
        cnt, idx, size = poster
        log(f'  harita posteri: {cnt} dilim ({idx[0]}..{idx[-1]}), {size[0]}x{size[1]} px')

    if pdf_only:
        for f in final:
            os.remove(f)
    shutil.rmtree(tmp, ignore_errors=True)
    return dict(pages=len(final), blanks=blanked, pdf=pdf_path)


# ---------------------------------------------------------------- toplu iş
def issue_meta(path):
    """DVD düzeninden (yıl klasörü + sayiN.bts) yıl/ay/sayı numarasını üretir."""
    m = re.search(r'sayi(\d+)\.bts$', os.path.basename(path), re.I)
    y = re.search(r'/(\d{4})/', path.replace(os.sep, '/'))
    if not (m and y):
        return None
    sayi, year = int(m.group(1)), int(y.group(1))
    if year == 1993:              # 1993/4 = Nisan 1993 = 1. sayı
        issue = sayi - 3
    else:                         # 1993'te 9 sayı var, sonrası aylık
        issue = 9 + (year - 1994) * 12 + sayi
    return year, sayi, issue


def batch(root, outdir, pdf_only=True, blanks_map=None, tiles_map=None, log=print):
    blanks_map = {**BLANKS, **(blanks_map or {})}
    files = []
    for dirpath, _, names in os.walk(root):
        for nm in names:
            if nm.lower().endswith('.bts'):
                files.append(os.path.join(dirpath, nm))
    files.sort()
    log(f'{len(files)} sayı bulundu')
    ok, fail = 0, []
    for f in files:
        meta = issue_meta(f)
        if not meta:
            log(f'atlandı (adlandırma tanınmadı): {f}')
            continue
        year, sayi, issue = meta
        name = f'{year}-{sayi:02d} Atlas Dergisi {issue:03d}'
        if os.path.exists(os.path.join(outdir, name + '.pdf')):
            log(f'{name}: zaten var, atlandı')
            continue
        log(f'{name}:')
        try:
            if pdf_only:                    # düz PDF çıktısı: jpg'ler geçici klasörde
                work = tempfile.mkdtemp(prefix='atlas-')
                try:
                    convert(f, work, blanks=blanks_map.get(issue, ()),
                            tiles_range=(tiles_map or {}).get(issue), name=name, log=log,
                            son_ek=(SON_EK[issue],) if issue in SON_EK else (),
                            atla=ATLA.get(issue, ()))
                    for suffix in ('.pdf', ' harita-poster.jpg'):
                        src = os.path.join(work, name + suffix)
                        if os.path.exists(src):
                            shutil.move(src, os.path.join(outdir, name + suffix))
                finally:
                    shutil.rmtree(work, ignore_errors=True)
            else:
                convert(f, os.path.join(outdir, name),
                        blanks=blanks_map.get(issue, ()),
                        tiles_range=(tiles_map or {}).get(issue), name=name, log=log,
                        son_ek=(SON_EK[issue],) if issue in SON_EK else ())
            ok += 1
        except Exception as e:                       # tek sayı patlarsa devam et
            log(f'  HATA: {e}')
            fail.append((name, str(e)))
    log(f'bitti: {ok} sayı, {len(fail)} hata')
    for n, e in fail:
        log(f'  ! {n}: {e}')
    return ok, fail


# ---------------------------------------------------------------- cli
def main():
    argv = sys.argv[1:]
    opts = {'blanks': (), 'tiles': None, 'out': None, 'batch': None,
            'pdf_only': '--pdf-only' in argv, 'keep_jpg': '--keep-jpg' in argv}
    for key in ('blanks', 'tiles', 'out', 'batch'):
        flag = '--' + key.replace('_', '-')
        if flag in argv:
            i = argv.index(flag)
            opts[key] = argv[i + 1]
            del argv[i:i + 2]
    args = [a for a in argv if not a.startswith('--')]

    blanks = {int(x) for x in opts['blanks'].split(',')} if opts['blanks'] else set()
    tiles = None
    if opts['tiles']:
        a, b = opts['tiles'].split('-')
        tiles = (int(a), int(b))

    if opts['batch']:
        root = opts['batch']
        outdir = os.path.expanduser(opts['out'] or 'AtlasPDF')
        os.makedirs(outdir, exist_ok=True)
        ok, fail = batch(root, outdir, pdf_only=not opts['keep_jpg'])
        sys.exit(0 if not fail else 1)

    if not args:
        print(__doc__)
        sys.exit(1)
    swf = args[0]
    out = args[1] if len(args) > 1 else os.path.splitext(os.path.basename(swf))[0]
    meta = issue_meta(swf)
    ek = (SON_EK[meta[2]],) if meta and meta[2] in SON_EK else ()
    at = ATLA.get(meta[2], ()) if meta else ()
    stats = convert(swf, out, blanks, opts['pdf_only'], tiles, son_ek=ek, atla=at)
    assert stats['pages'] > 0


if __name__ == '__main__':
    main()
