# Finora — V1.0 Vizyon ve Kapsam Kararı (2026-07-23)

## Karar
"Geniş V1.0" — README yol haritasındaki 5 killer feature tamamlanmadan
paketleme/çıkışa geçilmeyecek. Çekirdek (hesaplar, işlemler, bakiye matematiği,
AES-256 şifreleme, UI/tema sistemi) zaten tamamlanmış ve test edilmiş durumda;
kalan iş bu 5 özellik + teknik borçlar + paketleme.

## Mevcut Durum (referans: README.md, project_assessment.md, ANTIGRAVITY_TASKS*.md)
- ~17.500 satır kod, 3 aylık geliştirme.
- Çekirdek sistem (DB, servisler, bakiye/net servet hesabı, test altyapısı) oturmuş.
- UI: Tur 1-4 tamamlandı (Hesaplar/Kartlar sekmesi, diyalog yerleşimi,
  karanlık tema, RecycleView geçişi).
- İş modeli tavsiyesi (ayrı karar, henüz kesinleşmedi): tek seferlik
  Freemium/Premium lisans (39-49$), local-first olduğu için SaaS/abonelik
  modeline GİRİLMEMESİ öneriliyor.

## Sıralama ve Gerekçe

### 1. Teknik borçlar (önce — sonraki her özellik bunun üstüne kurulacak)
- [ ] Karanlık mod tercihinin kalıcı olması: `theme_style` da `theme_name` gibi
      `finora_config.json`'a yazılmalı (şu an sadece `theme_name` yazılıyor,
      uygulama her açılışta açık temayla başlıyor).
- [ ] `tests.test_ids` düzeltmesi (`ui/dashboard.kv:1640`,
      `app.active_category_type` binding hatası — Tur 3'ten önce de kırıktı).
- [ ] `ui/charts.py` grafik renklerinin karanlık/açık temaya uyarlanması
      (Tur 4'te incelenmedi, açık kaldı).

### 2. İstatistiksel özellikler (aynı altyapıyı paylaşır, birlikte yapılmalı)
- [ ] Otomatik abonelik radarı — tekrarlayan işlemlerin istatistiksel tespiti,
      "sessiz sızıntı" adaylarının yüzeye çıkarılması.
- [ ] İstatistiksel anomali tespiti — z-skoru tabanlı harcama sapması uyarıları.

### 3. Finansal Sağlık Skoru
- [ ] Tasarruf oranı, borç oranı, oynaklık bileşenlerinden skor hesaplama.
- [ ] Skor geçmişinin saklanması (yeni tablo/şema gerekebilir).
- Not: 2. maddedeki verilerden türetildiği için ondan sonra yapılması efor
  tasarrufu sağlar.

### 4. Bakiye zaman makinesi (point-in-time geçmiş & diff)
- [ ] Geçmiş anlık görüntü (snapshot) modeli — mevcut şemaya migration
      gerekip gerekmediği netleştirilmeli.
- [ ] Diff/karşılaştırma arayüzü.

### 5. What-if senaryo sandbox'ı (en soyut, en son)
- [ ] Mevcut RK4 (4. derece Runge-Kutta) servet projeksiyon motorunun
      parametrik hale getirilmesi (gelir/gider artış-azalış senaryoları).
- [ ] Senaryo karşılaştırma arayüzü.

### 6. Paketleme / Dağıtım (ürün donduktan sonra)
- [ ] Windows paket dağıtımının tamamlanması (build pipeline var, test
      ediliyor — PyInstaller vb.).
- [ ] Mac için imzalama/paketleme (varsa hedef).
- [ ] CI/CD ile otomatik `.exe`/`.dmg` üretimi (GitHub Actions).

## Ertelenmeyen / Değişmeyen Kısıtlar
- Local-first mimari korunacak: veriler cihazdan çıkmayacak, bulut/3. taraf
  sunucu yok.
- `services/*`, `database/*` gibi mantık katmanına dokunan değişiklikler
  büyük refaktör sayılır, ayrı dikkatle ele alınmalı (bkz. ANTIGRAVITY_TASKS
  dosyalarındaki "Değiştirilmeyecek dosyalar" prensibi).

## Sonraki Adım
Sıradaki iş: Madde 1 (teknik borçlar). Bitince madde 2'ye geçilecek.
