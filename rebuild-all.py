"""153 sayının tamamını bts'nin kendi sayfa dizisiyle yeniden üretir (paralel)."""
import glob
import os
import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, '/Users/user/Downloads/github-pemre/atlas-arsiv')
import atlas2pdf as A

OUT = '/Volumes/ebook/dergi/Atlas'


def one(bts):
    meta = A.issue_meta(bts)
    if not meta:
        return bts, 'ad tanınmadı'
    year, sayi, issue = meta
    name = f'{year}-{sayi:02d} Atlas Dergisi {issue:03d}'
    work = tempfile.mkdtemp(prefix='atlas-')
    try:
        st = A.convert(bts, work, pdf_only=True, name=name, auto_plan=True, log=lambda *a: None)
        for suffix in ('.pdf', ' harita-poster.jpg'):
            src = os.path.join(work, name + suffix)
            if os.path.exists(src):
                shutil.move(src, os.path.join(OUT, name + suffix))
        return name, st['pages']
    except Exception as e:
        return name, f'HATA: {e}'
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    everything = sorted(glob.glob('/Volumes/ATLAS/DVD1/*/*.bts')
                        + glob.glob('/Volumes/ATLAS 1/DVD2/*/*.bts'))
    args = sys.argv[1:]
    if args and not any('/' in a for a in args):        # sayı numarasıyla seç
        want = {int(a) for a in args}
        files = [b for b in everything if A.issue_meta(b) and A.issue_meta(b)[2] in want]
    else:
        files = args or everything
    print('sayı:', len(files), flush=True)
    ok = 0
    with ProcessPoolExecutor(4) as ex:
        for name, res in ex.map(one, files):
            ok += not str(res).startswith('HATA')
            print(f'{name}: {res}', flush=True)
    print('bitti, başarılı:', ok, '/', len(files))
