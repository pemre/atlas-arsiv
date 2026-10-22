# Atlas Dergisi Arşivi → PDF

**1993-2005 Atlas dergisi DVD'lerindeki Flash dosyalarını, doğru sayfa sırasıyla tek komutla PDF'e çevirir.**

![Birleştirilmiş interaktif harita posteri](docs/harita-poster-ornek.jpg)

Atlas'ın 2000'lerin başında verdiği DVD'lerde her sayı `sayi4.bts`, `sayi5.bts` … gibi dosyalarla geliyordu. Bunlar aslında birer **Flash (SWF)** dosyası: derginin tüm sayfaları JPEG olarak içine gömülü. Flash Player 2020'de öldüğü için bu arşiv bugün açılmıyor — ama içindeki sayfalar sapasağlam duruyor.

Bu araç o sayfaları **derginin kendi sırasıyla** çıkarır, siyah dolguları yerleştirir, interaktif haritayı poster olarak birleştirir ve hepsini tek PDF yapar.

---

## Neden "doğru sayfa sırası" bu kadar zor?

Denediyseniz bilirsiniz: `swfextract` ile görselleri çıkarırsınız, elinizde 200 küsur JPEG olur — ama sıra yanlıştır. Dergi sayfa 1 → 18 → 29 → 40 diye atlar. Elle sıralamak saatler sürer.

Sebep şu: bu dergilerde sayfalar Flash sahnesine (timeline) hiç konmaz, ActionScript ile çalışma anında çağrılır. Yani ne timeline sırası ne de görsel ID sırası işe yarar.

Gerçek sıra, SWF'in **`EXPORTASSETS`** etiketlerinde saklı: her sayfa sembolünün adı `p1`, `p2`, … `p107`. Ve işte tuzak:

```
Dosyada adlar alfabetik durur:   p1  p10  p100  p101  ...  p107  p11  p12  ...
Doğru sıra ise sayısal:          p1  p2   p3    p4    ...  p10   p11  p12  ...
```

Adlara göre sıralayan her araç (ve `swfextract`'ın çıktısı) sayfa sırasını mahveder. Bu proje adlardaki **sayıya** göre sıralar ve her sayfayı şu zincirle çözer:

```
"pN" export adı  →  sprite id  →  sprite'in PlaceObject2 çocuğu
                 →  DefineShape  →  bitmap fill id  →  JPEG
```

Ayrıca her sayı iki çözünürlükte gömülüdür (`pN` = 800×1067, `pageN` = 495×660). Sayfa kümesini **en çok etiketli aile** belirler (derginin tamamı), ama görsel **her sayfa için mevcut en yüksek çözünürlüklü kopyadan** alınır — yani **DVD'deki en iyi kopya** çıkar. Poster/ek gibi küçük ama büyük görselli kümeler (`pek`, `pa`, `pag` …) böylece elenir.

Bazı sayılarda yüksek çözünürlüklü aile eksiktir (örneğin 116 sayfanın 113'ü) ya da tek tük görselin JPEG başlığı bozuktur ("decompression bomb" hatası). Bu durumda o sayfa düşük çözünürlüklü ikizinden alınır; sayfa sırası ve sayısı bozulmaz, logda `uyarı:` satırı görürsünüz.

---

## Kurulum

```bash
# macOS
brew install swftools
python3 -m pip install pillow

# Debian/Ubuntu
sudo apt install swftools python3-pil
```

> `swfdump` ve `swfextract` gerekli (swftools paketinde gelir). `swfdump`, hangi şeklin hangi JPEG'i kullandığını söyler; JPEG'lerin kendisini `swfextract` çıkarır (paylaşılan JPEGTables'ı ekleyerek).

## Kullanım

**Tek sayı:**

```bash
python3 atlas2pdf.py sayi4.bts sayi4_pages
# → sayi4_pages/001.jpg … 107.jpg
# → sayi4_pages/sayi4_pages.pdf
# → sayi4_pages/harita-poster.jpg (varsa)
```

**Bütün DVD (asıl kullanım):**

```bash
python3 atlas2pdf.py --batch /Volumes/ATLAS/DVD1 --out ~/AtlasPDF
python3 atlas2pdf.py --batch /Volumes/ATLAS-1/DVD2 --out ~/AtlasPDF
```

Çıktı adları derginin gerçek sayı numarasıyla, düz dosya olarak üretilir:

```
1993-04 Atlas Dergisi 001.pdf
1994-01 Atlas Dergisi 010.pdf
…
1993-04 Atlas Dergisi 001 harita-poster.jpg   (varsa, ek dosya)
```

Bir sayı yarıda kalırsa aynı komutu tekrar çalıştırın: tamamlanmış sayılar (PDF var mı diye bakıp) atlanır.

### Seçenekler

| Seçenek | Ne yapar |
|---|---|
| `--batch <dizin>` | Klasördeki tüm `.bts` dosyalarını sırayla çevirir (DVD'nin kökü ya da `DVD1/` klasörü) |
| `--out <dizin>` | Toplu çıktı klasörü (varsayılan: `AtlasPDF`) |
| `--keep-jpg` | Toplu çevirimde JPEG'leri de saklar (sayı başına klasör açar; varsayılan: sadece PDF) |
| `--pdf-only` | Tek dosya çeviriminde de JPEG'leri siler |
| `--blanks 4,21,32` | Sayfa dizisi okunamazsa: belirtilen sayfalardan **sonra** siyah dolgu ekler (normalde gerekmez) |
| `--tiles 102-107` | Harita dilimlerini otomatik bulamazsa aralığı elle verir |

---

## Siyah dolgu sayfaları (eksik reklam sayfaları)

DVD'ye bazı reklam sayfaları hiç konmamış (o dönem yayın hakları vs.). Bu yüzden PDF iki sayfa yan yana görüntülendiğinde bir yerde sol-sağ eşleşmesi kayar ve tam sayfa fotoğraflar ortadan ikiye bölünmüş gibi görünür.

Eksik sayfaların **yeri tahmin edilmez: dosyanın kendisinde yazılıdır.** Flash uygulaması sayfa dizisini `setPages` içinde kurar ve DVD'ye aktarılmayan sayfanın yerine `dummy` sembolü koyar:

```
pageMask = [p1 … p34, dummy, p35 … p77, dummy, p78 … p84, dummy, p85 … p114]
```

`page_plan()` bu diziyi `swfdump -a` çıktısından okur; her `dummy` PDF'te siyah sayfa olur, sıra ve sayfa numaraları basılı dergideki gibidir. Hiçbir şey elle girilmez.

Doğrulama: 1. sayı için dizi `5, 23, 35, 67, 77, 85` verir — basılı dergiyle karşılaştırılıp elle sıralanmış PDF'teki 6 dolgu konumunun **birebir aynısı** (`test_atlas2pdf.py` içindeki `test_page_plan` bunu kilitler).

`--blanks` artık yalnız elle geçersiz kılma içindir (dizisi okunamayan bir dosya için); `BLANKS` sözlüğü de geri düşüş olarak duruyor.

## Harita posteri

Bazı sayılarda derginin interaktif haritası, kaydırılabilir bir panorama olarak sayfa sayfa gömülü — kenarlarında siyah barlar olan, üzerinde tipografi bulunmayan dilimler. Araç bunları otomatik tanır (yanlarda siyah bar + üst/alt bar yok + renkli illüstrasyon), **örtüşmeyi hesaplayarak** soldan sağa birleştirir ve kenar geçişlerini yumuşatarak `harita-poster.jpg` olarak kaydeder.

Dilimler PDF'te de aynen durur (dergideki sıralarıyla), poster sadece ek dosyadır.

---

## SSS

**Orijinal dosyalar korunuyor mu, yoksa yeniden mi sıkıştırılıyor?**
Korunuyor. SWF'in içindeki veri JPEG'dir (`DCTDecode`). `swfextract` bu sıkıştırılmış veriyi olduğu gibi alır, sadece dosyanın geçerli bir JPEG olması için paylaşılan `JPEGTables`'ı (nicemleme/Huffman tabloları) başına ekler. PDF de bu JPEG'i **yeniden sıkıştırmadan** gömer. Yani PDF'teki görüntü, DVD'deki bit akışının aynısıdır — tek bir nesil kayıp yok.

**Neden 800×1067? Daha büyüğü yok mu?**
DVD'de bu var: aynı sayfa 800×1067 (yüksek) ve 495×660 (düşük) olarak iki kez gömülü. Daha yüksek çözünürlük DVD'de yok — basılı dergiyi yeniden taramadan elde edilemez.

**Ne kadar sürer, ne kadar yer kaplar?**
Mac'te sayı başına ~10 saniye. PDF'ler sayı başına ~25-30 MB; `--pdf-only` ile toplam ~4 GB (153 sayı), JPEG'lerle birlikte ~10 GB.

**Hangi DVD'lerle test edildi?**
`Atlas_Dergisi_1993-2002_DVD1.iso` (117 sayı) ve `Atlas_Dergisi_2003-2012_DVD2.iso` (2003-2005, 36 sayı) — toplam 153 sayı. Dizin yapısı `DVD1/<yıl>/sayiN.bts` olan her arşivde çalışır.

**Bir sayıda hata alırsam?**
Toplu çevirim tek sayı patlarsa durmaz, hatayı yazıp devam eder ve sonunda listeler.

---

## 2006 sonrası: görsel klasörleri (`dvd2-images2pdf.py`)

2006'dan itibaren DVD'deki içerik Flash değil, **ayrı JPG sayfaları**. `.exe` bir
Macromedia Director sunucusudur, sayfaları gömmez — sıra bilgisi dosya adlarında
ve `.dir` içindeki arama indeksinde.

Sayfa numarası dosya adında yazılı:

| Ad | Anlam |
|----|-------|
| `ocak08_panorama.jpg`, `004_ocak.jpg` | 8. / 4. sayfa — yay mı, orana bakılır |
| `ocak11_12_panorama.jpg`, `01_page012_013.jpg` | 11-12 / 12-13 **yayı** |
| `01_page006.jpg` | 6. sayfa (2007 düzeni) |
| `KAPAK_ocak.jpg` | numarasız kapak → başa eklenir |

**Sıra kaynağı `.dir`'dir (2008-2012).** Her sayının kendi `<ay>.dir` dosyası var;
içindeki sıralı jpg adları Director cast sırası = uygulamanın gerçek sayfa sırası.
`dir_order()` bunu okur, aynı çekirdeğe düşen kopyalardan büyüğünü seçer
(`Ocak_014_015_L.jpg` ↔ `014_015.jpg`). Ad sıralamasına göre üretim 60 sayının
45'inde `.dir`'den farklı çıkıyordu — 1-3 dosya (2/3/4 kopyaları, boşluklu adlar),
biri 36 dosya. `.dir` görsel listesi içermeyen aylarda (2010-02, 2010-05, 2011-02,
2011-05) ve `.dir`'i hiç olmayan 2006-2007'de ad sıralamasına düşülür — bu 28 sayı
için "kesin" değil, aşağıdaki tabloya bak.

### Neyi kesin biliyoruz, neyi bilmiyoruz

| Dönem | Sayı | Sıra kaynağı | Kesinlik |
|-------|------|--------------|----------|
| 1993-2005 | 153 | `bts` içindeki `setPages`/`pageMask` dizisi | **kesin** — uygulamanın kendi sayfa dizisi |
| 2008 (10 ay), 2009-2010 (22 ay), 2012 (12 ay) | 56 | `<ay>.dir` içindeki sıralı jpg adları (Director cast sırası) | **kesin** — uygulama sayfaları bu sırayla yüklüyor |
| 2010-02, 2010-05, 2011-02, 2011-05 | 4 | dosya adı sırası | **kesin değil** — `.dir` var ama yalnız `<kayit><sayfa>` metin indeksi (39-51 kayıt); sayfa *numaralarını* doğruluyor, *sırayı* vermiyor |
| 2006, 2007 | 24 | yalnız dosya adı sırası | **kesin değil** — aşağıdaki arama boş çıktı |

2006/2007 için indeks arayışı (sonuç: **indeks yok, array yok**):

- `atlas.exe`, `screensaver.exe`, `alPicView.ocx` dahil yıl klasöründeki tüm görsel-dışı
  dosyalar (exe/ocx/dll/u32/xmo/dat/ini) hem tam ad hem uzantısız ad için tarandı → **0 eşleşme**.
- SWF taraması: dosya başından değil **her ofsetten** `FWS`/`CWS`/`ZWS` imzası arandı ve
  adaylar doğrulandı (sürüm 1-60, uzunluk makul, CWS'te `0x78` zlib başlığı) → **geçerli aday 0**.
- `atlas.exe`'nin son 13 MB'ı PE dışında bir **paketli katman**: başlık `PCRS` +
  `0xAFBCADAC`, içinde Lua bytecode ve bitmap chunk'ları var; Director movie 4CC'si
  (`RIFX`/`XFIR`/`CASt`/`Lscr`/`VWSC`) veya düz metin dosya adı **yok**, string'ler gizlenmiş.
- Flash projector **değil**: `Flash`, `Shockwave`, `Zinc`, `SWF Studio`, `Screenweaver`,
  `mProjector` string'lerinin hiçbiri yok; Flash projector EXE'lerinin sonundaki
  `0xFA123456` işareti de yok (`tail -c 8` → `1a6d3c01a90d3315`). Yani "bozuk projector"
  değil, hiç projector olmamış.
- Kabuk **VB6**: `alPicView.ocx` = `MSVBVM60.DLL` ile çalışan 86 KB'lık VB6 ActiveX
  görüntüleyici (`GetOpenFileName`, "Zoom array"); içinde ne görsel adı ne klasör listesi
  var. Klasördeki `*.U32`, `*.XMO` (Director Xtras) artıkları eski sürümden kalma.
- Belirleyici bulgu: exe `FindFirstFile` çağırıyor — sayfa listesini **çalışma anında
  klasörden** okuyor. Yani saklanmış bir sayfa dizisi yok; sıra = klasör listeleme sırası
  = alfabetik, ki adlar sayfa numarasını taşıdığı için numara sırasıyla aynı. `Dergi/Thumbs/<sayı>/` sayfa adlarının tam listesini
veriyor — yalnız **hangi adlar var** sorusu için kullanıldı, sıra için değil. Thumbs
damgaları sayfa numarasıyla artıyor (2006/154'te 70/73, 2007/166'da 68/70 çift artan)
ama bu **kanıt sayılmaz**: küçük resimleri üreten araç klasörü alfabetik listeliyorsa
aynı sonucu verir; yani kendi kendini doğrulayan halka.

**Bilinen eksik sayfalar:** 2007-12 (sayı 177) — `Thumbs` klasöründe 4 yay var
(`12_pages_48_49`, `12_pages_96_97`, `12_pages_98_99`, `12_pages_0118_0119`) ama
`Images` klasöründe yok; DVD'ye konmamış, PDF'te o 4 sayfa eksik. 2006'nın 6 sayısında
kapak yalnız `Thumbs`'ta (Images'ta yok) — kapak `images/kapaklar`'dan geldiği için
PDF'te mevcut.

**Yay tespiti ada değil görsele dayanır:** yay görselleri iki sayfa genişliğinde
(en-boy oranı ~1,5), tek sayfa ~0,76. `is_spread()` oranı 1,2'nin üstündeyse iki
sayfa sayar. Adlar yıldan yıla değişiyor (2009 ve 2012'de dosyalar tek sayfa,
2008'de karışık), oran değişmiyor.

Klasör düzeni de yıla göre değişir:

```
2006-2007  <yıl>/Dergi/Images/<sayı no>/
2008       <yıl>/content/aylar/<ay>_1500/      (_1000 düşük çözünürlük)
2009-2010  <yıl>/images/large/<NN>_<Ay>/
2011       <yıl>/images/large_2/<NN>_<Ay>/
2012       <yıl>/images/_Large/<NN>_<Ay>/
```

- **Kapak** çoğu zaman sayfa klasöründe değil: `images/kapaklar/01_ocak.jpg`
  (veya 2012'de `_kapaklar/Ocak_001.jpg`). Bazı sayılarda klasörün içinde iki
  kapak dosyası bulunur (`KAPAK_Ocak.jpg` + `AT_202_KAPAK.jpg`) — en büyüğü
  seçilir, kapak PDF'e **bir kez** girer.
- **Eksik sayfa = numara atlaması, ama varsayılan olarak DOLDURULMAZ.** 2006 sonrası
  DVD'ler delikli tarama: bir sayıda 84 görselin karşılığı 141 basılı sayfa çıkıyor,
  yani sayfaların ~%40'ı hiç taranmamış (çoğu yayın yalnız sol yarısı var). Oraya siyah
  basmak dergiyi olduğundan farklı gösterir; bu yüzden görseller sırayla konur.
  Gerçekten dolgu istiyorsan `--blanks` ver.
- **Yay görselleri bölünmez**, tek geniş sayfa olarak girer.

### `.dir` indeksi ile doğrulama

`.dir` dosyasının içinde her metinli sayfa için `<kayit><sayfa>N</sayfa><data>…`
kaydı var (sayfa numarası + sayfanın metni). Bu, Flash dönemindeki `pageMask`
dizisinin karşılığı: sıra için dosya adlarına güvenilebilir, indeks onları
doğrular (2010-01 ve 2009-01'de 51 sayfanın 50'si birebir; tek fark kapak).

### Kullanım

```bash
python3 dvd2-images2pdf.py --year 2010 --out ~/AtlasPDF
```

### Tuzak: eksik ISO

DVD2 ISO'su eksik indirilmişse (bildirilen hacim > dosya boyutu) diskin **sonundaki**
sayılar `Input/output error` verir. Kontrol:

```python
struct.unpack('<I', open(iso,'rb').read(2048*17)[80:84])[0] * 2048  # beklenen boyut
os.path.getsize(iso)                                                # gerçek boyut
```

Eşit değilse ISO'yu yeniden oluşturun ya da diski doğrudan bağlayıp `--root` verin.

## Katkı

- Başka bir sayı için doğrulanmış `--blanks` konumları bulduysanız `BLANKS` sözlüğüne ekleyip PR açın.
- Farklı bir DVD/dergi ailesi (örn. farklı sembol adlandırması) ile çalıştıysanız issue açın.

## Telif

Bu depo **yalnızca bir dönüştürücüdür**; dergi içeriğini barındırmaz ve dağıtmaz. Atlas dergisinin tüm içeriği ilgili hak sahiplerine aittir. Çıkardığınız PDF'leri kişisel arşivinizde tutun, dağıtmayın.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
