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
      StringProperty("income")` eklendi, stub sözleşmesi tamamlandı. TCP-Xvfb
      ile gerçek OpenGL pencere üzerinde görsel/headless doğrulama da yapıldı
      — KV/OpenGL smoke testi geçti.
- [x] `ui/charts.py` grafik renklerinin (eksen, ızgara, etiket, boş-veri
      halkası) temaya uyarlanması + tema değişiminde trend/pasta/çubuk
      grafiklerin veriyi koruyarak yeniden çizilmesi. Gelir/gider ve kategori
      renkleri semantik olduğu için kasıtlı olarak değiştirilmedi.

**Doğrulama:** Python sözdizimi kontrolleri geçti.

**SavingsService test hataları — çözüldü:**
- [x] Test bakiyesi 10.000 TL'ye ayarlandı, her test sonunda özgün bakiye geri
      yükleniyor. Sonuç: SavingsService 6/6, tam paket 120/120 yeşil,
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
- [x] Haftalık, iki haftada bir ve üç aylık adayların otomatik takibe
      alınması. Vade motoru `weekly`, `biweekly`, `monthly`, `quarterly` ve
      `yearly` periyotlarını; ay sonu ve artık yıl sınırlarını destekliyor.
      Bilinmeyen periyotlar sessizce aylık sayılmak yerine reddediliyor.
- [x] Anomaliler için kalıcı “GÖRDÜM” akışı ve `anomaly_dismissals`
      migration'ı. Gizleme transaction kimliğiyle idempotent uygulanıyor ve
      sonraki dashboard yenilemelerinde aynı anomali eleniyor.

### 3. Finansal Sağlık Skoru
- [x] Tasarruf oranı, borç oranı ve oynaklık bileşenlerinden ağırlıklı skor
      hesaplama.
- [x] Güncel skorun anasayfa kartında gösterilmesi.
- [x] Skor geçmişinin `financial_health_history` tablosunda saklanması ve
      `get_health_history(limit=30)` ile okunması.
- [x] Son 30 günlük sağlık skoru kaydını gösteren tema-duyarlı mini
      trend/sparkline grafiği. Aynı gün içindeki dashboard yenilemeleri yeni
      satır üretmek yerine günlük kaydı güncelliyor; eski aynı-gün tekrarları
      migration sırasında tek kayda indiriliyor.

**Madde 3 — TAMAMLANDI.**

### 4. Bakiye zaman makinesi (point-in-time geçmiş & diff)
- [x] `daily_balance_snapshot` + `balance_events` defteriyle geçmiş anlık
      görüntü/replay modeli; migration guard ve eksik defter healing/backfill.
- [x] Son 30 günlük hızlı diff görünümü ile iki tarih seçicili özel tarih
      aralığı karşılaştırması.
- [x] Tek tarih seçerek gün sonu toplam bakiye, birikim toplamı ve hesaplama
      kaynağını (`snapshot`/`replay`) gösteren point-in-time görünümü.
- [x] Defter başlangıcından önceki tarihler için yanıltıcı sıfır yerine açık
      “kayıt yok” durumu.

**Madde 4 — TAMAMLANDI.**

### 5. What-if senaryo sandbox'ı (en soyut, en son)
- [x] RK4 (4. derece Runge-Kutta) servet projeksiyon motorunun Kivy'den
      bağımsız `services/projection_service.py` katmanına taşınması; günlük
      seri ve geriye uyumlu nihai değer API'leri.
- [x] Gelir/gider yüzde değişimi, 30/90/365 günlük ufuk ve imzalı tek
      seferlik gelir/gider parametreleriyle taban + what-if simülasyonu.
- [x] Araçlar sekmesindeki What-If Sandbox diyaloğu, çok-serili karşılaştırma
      grafiği ve taban senaryoya göre nihai fark/negatif varlık uyarısı.
- [x] Analitik çözüm karşılaştırması, delta uygulaması, negatif senaryo,
      365 günlük kararlılık ve headless mixin veri-akışı testleri.

**Madde 5 — TAMAMLANDI.** Görsel doğrulama: TCP-Xvfb üzerinden gerçek OpenGL
pencerede What-If Sandbox, Bakiye Geçmişi ve MDDatePicker akışları test
edildi (ekran görüntüleri: `finora_scenario_smoke0003.png`,
`finora_history_smoke0004.png`, `finora_datepicker_smoke0002.png`). Bu turda
ayrıca Python 3.14'te `MDDatePicker`'ı çökerten `ast.Str` uyumsuzluğu
giderildi, tarih seçici metinleri TR/EN sistemine bağlandı, What-If diyaloğu
800×600 ekrana sığacak şekilde kompaktlaştırıldı.

**Ortam notu:** Standart `xvfb-run` kullanımını kalıcı olarak düzeltmek için
(bu oturumda TCP-Xvfb alternatifiyle aşıldı) `/tmp/.X11-unix` sahiplik/izin
düzeltmesi gerekiyor — dilersen kendi terminalinde bir kerelik çalıştır:
`sudo chown root:root /tmp/.X11-unix && sudo chmod 1777 /tmp/.X11-unix`.

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
      durumları. Aboneliğe ekleme ve anomali gizleme eylemleri için headless
      testler eklendi; widget render ve hata yolları hâlâ açık.
- [ ] İşlem hacmi birkaç bine ulaştığında insights yenileme süresini ölç.
      Şimdilik hesaplar arka plan thread'inde çalıştığı için acil değil;
      gerekirse sonuçları yeni işlem/değişiklik oluşana kadar cache'le.

## Sonraki Adım
Beş killer feature de (Madde 1-5) tamamlandı, tam otomatik paket 120/120
yeşil. Kalan tek şey Madde 6 — paketleme/dağıtım. Kalite takibindeki iki
açık madde (insights widget render testleri, performans ölçümü) V1.0'ı
bloklamıyor; paketlemeyle paralel ya da sonrasında ele alınabilir.

1. Madde 6 (Windows paketleme, CI/CD) üzerinde ilerle.
2. İstersen paralel olarak insights widget render/hata testlerini tamamla.
