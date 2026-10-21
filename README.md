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

Ayrıca her sayı iki çözünürlükte gömülüdür (`pN` = 800×1067, `pageN` = 495×660). Araç **en çok etiketli aileyi** (derginin tamamı), eşitlik durumunda yüksek çözünürlüklü olanı seçer — yani **DVD'deki en iyi kopya** çıkar. Poster/ek gibi küçük ama büyük görselli kümeler (`pek`, `pa`, `pag` …) böylece elenir.

Nadir de olsa DVD'de başlığı bozuk bir JPEG olabiliyor (Python "decompression bomb" hatası verir). Böyle bir sayfada araç aynı sayfanın düşük çözünürlüklü ikizini kullanır, sayfa sırası bozulmaz; logda `uyarı:` satırı görürsünüz.

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
| `--blanks 4,21,32` | Belirtilen sayfalardan **sonra** siyah dolgu sayfası ekler |
| `--tiles 102-107` | Harita dilimlerini otomatik bulamazsa aralığı elle verir |

---

## Siyah dolgu sayfaları

DVD'ye bazı reklam sayfaları hiç konmamış (o dönem yayın hakları vs.). Bu yüzden PDF iki sayfa yan yana görüntülendiğinde bir yerde sol-sağ eşleşmesi kayar ve tam sayfa fotoğraflar ortadan ikiye bölünmüş gibi görünür.

`--blanks` ile eksik sayfaların yerine siyah sayfa konur, böylece çift sayfa görünümü (yay ve karşı sayfa) dergideki gibi olur.

**1. sayı (Nisan 1993) için doğrulanmış konumlar script içinde hazır** (`BLANKS = {1: (4, 21, 32, 63, 72, 79)}`), toplu çevirimde otomatik uygulanır → 107 sayfa + 6 dolgu = **113 sayfa**.

Başka bir sayı için konum bulmak isterseniz: PDF'i çift sayfa görünümünde açın, kaymanın olduğu yeri not edin ve sayfa numarasını `--blanks`'a yazın. (Dolgu sayfaları PDF'e dahildir, JPEG olarak da siyah üretilir.)

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

## Katkı

- Başka bir sayı için doğrulanmış `--blanks` konumları bulduysanız `BLANKS` sözlüğüne ekleyip PR açın.
- Farklı bir DVD/dergi ailesi (örn. farklı sembol adlandırması) ile çalıştıysanız issue açın.

## Telif

Bu depo **yalnızca bir dönüştürücüdür**; dergi içeriğini barındırmaz ve dağıtmaz. Atlas dergisinin tüm içeriği ilgili hak sahiplerine aittir. Çıkardığınız PDF'leri kişisel arşivinizde tutun, dağıtmayın.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
