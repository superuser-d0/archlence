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
- [x] Karanlık mod tercihinin kalıcı olması — `finora_config.json` içinde
      `display.style` alanına yazılıyor, açılışta okunup geri yükleniyor.
- [x] `tests.test_ids` düzeltmesi — `IdsApp`'e `active_category_type =
      StringProperty("income")` eklendi. Doğrulama notu: ortamda video aygıtı
      olmadığı için headless çalıştırma denemesi KV hatasına ulaşmadan ortam
      seviyesinde durdu; kod incelemesiyle doğrulandı, görsel/headless
      doğrulama (`xvfb-run` vb.) hâlâ açık.
- [x] `ui/charts.py` grafik renklerinin (eksen, ızgara, etiket, boş-veri
      halkası) temaya uyarlanması + tema değişiminde trend/pasta/çubuk
      grafiklerin veriyi koruyarak yeniden çizilmesi. Gelir/gider ve kategori
      renkleri semantik olduğu için kasıtlı olarak değiştirilmedi.

**Doğrulama:** Python sözdizimi kontrolleri geçti.

**SavingsService test hataları — çözüldü:**
- [x] Test bakiyesi 10.000 TL'ye ayarlandı, her test sonunda özgün bakiye geri
      yükleniyor. Sonuç: SavingsService 6/6, tam paket 97/97 yeşil,
      `git diff --check` temiz.

**Madde 1 — TAMAMLANDI.**

### 2. İstatistiksel özellikler (aynı altyapıyı paylaşır, birlikte yapılmalı)
- [x] Otomatik abonelik radarı — tekrarlayan işlemlerin istatistiksel tespiti,
      "sessiz sızıntı" adaylarının yüzeye çıkarılması, aday takibi ve kalıcı
      yoksayma akışı.
- [x] İstatistiksel anomali tespiti — z-skoru tabanlı harcama sapması
      uyarıları ve anasayfa kartları.
- [x] Şifreli `amount`/`description` alanları SQL'de toplanmadan Python'da
      çözülüp hesaplanıyor.
- [x] Servis katmanı tolerans, düzensiz aralık, eşik ve kalıcılık
      senaryolarıyla test ediliyor.

**Madde 2 — TAMAMLANDI (V1 çekirdeği).**

İyileştirme kararları:
- [ ] Haftalık, iki haftada bir ve üç aylık adayların otomatik takibe
      alınması. Mevcut `recurring_payments` vade motoru yalnız `monthly` ve
      `yearly` ilerletebildiği için bu değişiklik mantık katmanında ayrıca
      tasarlanmalı. O zamana kadar bu adaylar tespit edilir ve kalıcı
      yoksayılabilir, fakat otomatik takibe alınamaz.
- [ ] Anomaliler için kalıcı “gördüm/gizle” akışı ve
      `anomaly_dismissals` benzeri migration. Şu anda aynı tarihsel anomali
      sonraki yenilemelerde yeniden gösterilebilir.

### 3. Finansal Sağlık Skoru
- [x] Tasarruf oranı, borç oranı ve oynaklık bileşenlerinden ağırlıklı skor
      hesaplama.
- [x] Güncel skorun anasayfa kartında gösterilmesi.
- [x] Skor geçmişinin `financial_health_history` tablosunda saklanması ve
      `get_health_history(limit=30)` ile okunması.
- [ ] Son 30 sağlık skoru kaydını gösteren mini trend/sparkline grafiği.
      Veri kaynağı hazır; eksik kısım `insights_mixin.py` ve
      `ui/dashboard.kv` içindeki görselleştirme bağlantısı.

**Madde 3 — HESAPLAMA, KALICILIK VE GÜNCEL SKOR UI TAMAMLANDI; trend
görselleştirmesi açık.**

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

## Kalite ve Performans Takibi
- [ ] `mixins/insights_mixin.py` render ve kullanıcı eylemleri için UI/mixin
      testleri: sağlık skoru render'ı, aboneliğe ekleme/yoksayma ve hata
      durumları. Mevcut kapsam ağırlıklı olarak servis katmanında.
- [ ] İşlem hacmi birkaç bine ulaştığında insights yenileme süresini ölç.
      Şimdilik hesaplar arka plan thread'inde çalıştığı için acil değil;
      gerekirse sonuçları yeni işlem/değişiklik oluşana kadar cache'le.

## Sonraki Adım
1. Sağlık skoru trend grafiğini tamamla (veri ve kalıcılık hazır).
2. Insights mixin/UI akışları için test güvenlik ağı ekle.
3. Haftalık/iki haftalık/üç aylık abonelik takibi ile anomali gizleme
   özelliklerinin V1.0 kapsamına girip girmediğini kararlaştır.
4. Ardından Madde 4 (bakiye zaman makinesi), Madde 5 (what-if sandbox) ve
   ürün donduğunda Madde 6 (paketleme) sırasıyla ilerle.
