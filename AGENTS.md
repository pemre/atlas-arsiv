# AGENTS.md

Bu depo tek dosyalık bir araç: `atlas2pdf.py` + `README.md`. Yeni soyutlama, framework
veya klasör eklemeyin.

## Kurallar

1. **Davranış değişirse README aynı commit'te güncellenir.** Hangi davranış: CLI
   seçenekleri (`--batch`, `--blanks`, `--tiles`, `--pdf-only`, `--keep-jpg`), çıktı
   adlandırması (`YYYY-MM Atlas Dergisi NNN.pdf`), sayfa sırası kuralı, siyah dolgu
   konumları, poster üretimi.
2. **Tek doküman kuralı**: README dışında `docs/*.md` açmayın; `docs/` yalnızca görsel
   barındırır.
3. **Sorun giderme girdisi = belirti + sebep + çözüm** biçiminde README'ye eklenir.
4. **Test**: yeni test framework'ü yok. `python3 test_atlas2pdf.py` (assert tabanlı,
   SWF gerektirmez) yeşil kalmalı. SWF'e bağlı bir davranışı değiştirdiyseniz gerçek bir
   `.bts` ile bir kez elle çalıştırıp sayfa sayısını doğrulayın.
5. **Sayfa sırası kuralı bozulmamalı**: sıra `EXPORTASSETS` adlarındaki **sayıya** göre
   sıralanır. Alfabetik sıralama (`p1, p10, p100…`) tüm arşivi bozar; ID sırası da yanlıştır.
6. **Kullanıcı verisi**: bu araç kullanıcının DVD'lerini okur, hiçbir yere yüklemez;
   ağ çağrısı yoktur. Bunu ekleyecek bir değişiklik ayrıca tartışılmalı.
7. **Telif**: depo dergi içeriği barındırmaz. Örnek çıktı olarak yalnızca kendi ürettiğimiz
   poster görseli (`docs/harita-poster-ornek.jpg`) durur; tam sayfa/dizi PDF eklemeyin.

## Değişiklik sonrası kontrol listesi

- `python3 test_atlas2pdf.py`
- Gerçek bir sayı ile tek dosya çevirimi (sayfa sayısı + PDF sayfa sayısı eşit mi)
- README güncellendi mi?
