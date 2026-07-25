# Archlence — V1.0 Vizyon ve Kapsam Kararı (2026-07-23)

## İsim ve marka kararı (2026-07-23)
Ürünün adı **Archlence** olarak kesinleştirildi. Ad; ayırt edilebilir,
uluslararası kullanıma uygun ve fintech alanında özgün bir marka kimliği
oluşturacak şekilde seçildi.

**Marka kimliği:** Siyah zemin (`#141414`) üzerine beyaz, "A" harfini
kırılgan-yaprak (petal) formlarından kuran bir monogram; merkezden dışa
yayılan, yarı saydam ek ışınlarla desteklenmiş "patlama" efekti (bkz.
`assets/icon_source.svg`). Bu SVG masaüstü uygulama ikonu için nihai kaynak.

**Uygulanan değişiklikler (bu oturumda):**
- [x] `README.md` — başlık, özellik listesi, yol haritası ve iletişim adresi
      Archlence'e güncellendi; eski isim değişikliği not olarak eklendi.
- [x] `archlence.spec` — `name="Archlence"`, `icon="assets/icon.ico"`.
- [x] `.github/workflows/build-windows.yml` — artifact adı ve `dist/` yolu
      Archlence'e güncellendi.
- [x] `assets/icon_source.svg` — nihai ikon vektör kaynağı kaydedildi.

- [x] `icon_source.svg` kaynak alınarak masaüstü `icon.png` ve çok boyutlu
      `icon.ico` üretildi.
- [x] Kaynak kod, UI metinleri, testler, yapılandırma ve paketleme
      tanımlayıcıları Archlence adına geçirildi.

**Rename + QA denetimi sonucu (2026-07-23, ayrı bir AI turu):**
- [x] 39 mantıksal dosya/varlık etkilendi (34 düzenleme, 2 dosya yeniden
      adlandırma, 3 ikon varlığı). `FinoraApp` → `ArchlenceApp`,
      `finora.spec` → `archlence.spec`. Config için eski dosyayı
      `archlence_config.json`'a kopyalayan migration yaklaşımı kullanıldı
      (kullanıcı verisi kaybolmadı). Kriptografik sabitlerin byte
      değerlerine dokunulmadı (davranış korundu). Son taramada kapsam dışı
      klasörler hariç literal "Finora" eşleşmesi: **0**.
- [x] Görsel/fonksiyonel QA — 1 hata bulundu ve düzeltildi: sağlık skoru
      sparkline'ı doğru ebeveyn zincirindeydi ama `MDFloatLayout` içinde
      konumlanmamıştı (`pos=(0,0)` kalıyordu), bu yüzden canvas'ı pencerenin
      sol-altına, alt navigasyonun üzerine çiziliyordu. `ui/dashboard.kv:664`
      içine `pos_hint: {"x": 0, "y": 0}` eklenerek düzeltildi. Tüm ekranlar
      (Home, Varlıklarım, Kartlarım, Araçlar, Ayarlar) + What-If (31 grafik
      noktası), Bakiye Geçmişi ve `MDDatePicker` gerçek SDL2/OpenGL
      penceresinde tekrar tarandı, başka taşma/yanlış parent bulunmadı.
- [x] Doğrulama: `compileall` geçti, `git diff --check` temiz, **121/121**
      test yeşil. Test paketinde işlevsel hataya yol açmayan, zararsız bir
      `ResourceWarning: unclosed database` var — kalite takibine not düşüldü.

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
- [x] Karanlık mod tercihinin kalıcı olması — `archlence_config.json` içinde
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
- [x] Aynı gün içindeki dashboard yenilemeleri yeni satır üretmek yerine
      günlük kaydı güncelliyor; eski aynı-gün tekrarları migration sırasında
      tek kayda indiriliyor.

**Madde 3 — TAMAMLANDI.**

**Kart düzeltmesi (2026-07-23, ayrı bir tur):** Kullanıcı, kart altındaki
eğri sparkline'ın bir işlevi olmadığını belirtti; kaldırıldı. Aynı turda,
gerçek veri olmadığında (`total_income <= 0 and total_expense <= 0`)
`_score_savings_rate`/`_score_debt_ratio`/`_score_volatility`'nin döndürdüğü
nötr `50.0` varsayılanının ekranda sanki gerçek bir "50/Orta" değerlendirmesi
gibi gösterildiği, yanıltıcı bir veri bütünlüğü sorunu da düzeltildi.

- [x] `ui/dashboard.kv`'den sparkline ve boş-geçmiş etiketi kaldırıldı, kart
      yüksekliği 212dp → 150dp. `HealthScoreSparkline` sınıfı (`ui/charts.py:310`)
      ve `get_health_history(limit=30)` ileride kullanılmak üzere korundu.
- [x] `insufficient_data` eşiği: `total_income <= 0 and total_expense <= 0`
      (yalnızca lookback penceresinde hiç gerçek gelir/gider yoksa). Daha katı
      bir işlem/gün sayısı eşiği kasıtlı olarak seçilmedi — tek taraflı
      gelir/gider de gerçek veridir, az verisi olan kullanıcıyı gereksiz
      engellemez, gerçek hesaplamayla 50 alan kullanıcı "veri yok" durumuyla
      karışmaz.
- [x] Yetersiz veri durumunda `compute_financial_health_score` artık
      `{"score": None, "breakdown": {}, "computed_at": ..., "insufficient_data": True}`
      döndürüyor ve geçmiş tablosuna yazmıyor. UI: skor "--", etiket "Yeterli
      veri yok", açıklama "Skor hesaplamak için henüz yeterli veri yok. Birkaç
      işlem ekleyince burada görünecek.", progress bar gizli.
- [x] Değişen dosyalar: `services/insights_service.py:473`,
      `mixins/insights_mixin.py:139`, `ui/dashboard.kv:598`, `ui/i18n.py`,
      `main.py`, `tests/test_insights_service.py`, `tests/test_insights_mixin.py`.
- [x] Doğrulama: 126/126 test yeşil, `compileall` geçti, `git diff --check`
      temiz. Gerçek SDL2/OpenGL doğrulaması: işlemsiz profilde "--"/"Yeterli
      veri yok", gerçek veride skor 90/"Çok İyi"; her iki ekranda da
      `health_trend_chart` ID'si yok.

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
edildi (ekran görüntüleri: `archlence_scenario_smoke0003.png`,
`archlence_history_smoke0004.png`, `archlence_datepicker_smoke0002.png`). Bu turda
ayrıca Python 3.14'te `MDDatePicker`'ı çökerten `ast.Str` uyumsuzluğu
giderildi, tarih seçici metinleri TR/EN sistemine bağlandı, What-If diyaloğu
800×600 ekrana sığacak şekilde kompaktlaştırıldı.

**Ortam notu:** Standart `xvfb-run` kullanımını kalıcı olarak düzeltmek için
(bu oturumda TCP-Xvfb alternatifiyle aşıldı) `/tmp/.X11-unix` sahiplik/izin
düzeltmesi gerekiyor — dilersen kendi terminalinde bir kerelik çalıştır:
`sudo chown root:root /tmp/.X11-unix && sudo chmod 1777 /tmp/.X11-unix`.

### 6. Paketleme / Dağıtım (ürün donduktan sonra)

**Kapsam kararı: V1.0 yalnızca Windows + Linux hedefler. Mac kapsam dışı**
(karar tarihi: bugün) — `.dmg`/notarization işi ayrı bir karara bağlanana
kadar bu listeden çıkarıldı.

**Windows — mevcut `archlence.spec` + `.github/workflows/build-windows.yml`
üzerinden tamamlanacaklar (2026-07-23 denetim raporu):**
- [x] Uygulama ikonu — çok boyutlu `assets/icon.ico` (16/32/48/64/128/256px)
      ve `assets/icon.png` (1024×1024 RGBA) üretildi, spec'e bağlandı
      (`archlence.spec:67`).
- [ ] Derleme sonrası smoke test — hâlâ eksik. İş akışı yalnızca derleyip
      artifact yüklüyor, `Archlence.exe`'nin gerçekten açılıp çökmediğini
      doğrulamıyor.
- [ ] Python sürüm tutarlılığı — hâlâ eksik. Yerel ortam gerçekte 3.14.6,
      CI 3.12 kuruyor; bir karar/uyumluluk matrisi yok.
- [ ] Sürüm/adlandırma — hâlâ eksik. Git tag yok, artifact sabit
      `Archlence-Windows` adıyla çıkıyor.
- [~] Kod imzalama — uygulanmadı ama V1.0 için zorunlu olmadığı ve
      ertelendiği bilinçli olarak belgelendi.
- [~] Kurulum sihirbazı (Inno Setup/NSIS) — tanımlı değil ama V1.0 dışı
      ayrı karar olarak belgelendi.

**Linux — sıfırdan kurulacak (hepsi hâlâ eksik):**
- [ ] `build-linux.yml` — yok, yalnızca `build-windows.yml` var.
- [ ] `.desktop` dosyası — bulunamadı.
- [ ] AppImage üretimi — script/workflow/tanım yok.
- [ ] Linux'a uygun spec ayarları — `archlence.spec` hâlâ doğrudan
      Windows'a özgü `kivy_deps.sdl2`/`glew` paketlerini içe aktarıyor,
      platforma göre dallanmıyor.
- [ ] Windows'takiyle aynı Python sürüm tutarlılığı kontrolü.

**Rename denetimi:** Kapsam dışı klasörler hariç tutularak yapılan taramada
sıfır kalan "Finora" referansı bulundu. Proje klasörü adı
(`Documents/finora`) ve `graphify-out/` önbelleği talimat gereği bilinçli
olarak değiştirilmedi (önbellek daha sonra silinip yeniden üretilmeli).

## Güvenlik — yerel PIN sistemi (2026-07-23, ayrı bir tur)

Kullanıcının kendi tespit ettiği bir GUI eksikliği ("kayıt olma yok, hesap
oluşturma butonu işlevsiz") araştırılırken daha ciddi bir güvenlik açığı
ortaya çıktı: giriş ekranı, kod içine gömülü SABİT bir `ADMIN_HASH` (her
kurulumda aynı) ve tuzsuz SHA-256 kullanıyordu; ayrıca `main.py::check_login`
içinde hash kontrolünü tamamen atlayan literal bir `"admin_secret"` arka
kapı şifresi vardı. Bunlar tamamen kaldırıldı.

- [x] Gerçek yerel PIN sistemi kuruldu: ilk açılışta `pin_setup` ekranı,
      4-12 haneli PIN + tekrar, kurulum başına `secrets.token_hex(16)` ile
      128-bit rastgele tuz, `hmac.compare_digest` ile zamanlama saldırısına
      dayanıklı karşılaştırma. Düz PIN hiçbir yere yazılmıyor.
- [x] Sabit `ADMIN_HASH` ve literal `"admin_secret"` arka kapısı tamamen
      kaldırıldı (`security/security_service.py:14`, `main.py:1155`).
- [x] İşlevsiz "hesap oluştur" butonu ve tüm e-posta ile "şifremi unuttum"
      akışı (`ui/dashboard.kv`) kaldırıldı — local-first mimaride zaten
      kavramsal olarak anlamsızdı. Kullanıcı adı alanı da kaldırıldı
      (tek-kullanıcılı uygulamada gereksizdi).
- [x] PIN kurtarma yolu: giriş öncesi Ayarlar menüsüne "PIN ve Verileri
      Sıfırla" eklendi — PIN/tuzu, tüm kullanıcı tablolarını, saklı kart
      numarası/SKT/CVC alanlarını ve işlem/varlık/borç/hedef/geçmiş/içgörü
      kayıtlarını temizliyor (dil/tema tercihi korunuyor), sonra tekrar
      `pin_setup`'a yönlendiriyor.
- [x] Gizli `screens/admin_screen.py` paneli tamamen kaldırıldı — gerekçe:
      işlevleri (CSV export, sıfırlama) zaten Ayarlar'da daha eksiksiz
      şekilde mevcuttu, üstelik admin paneli şifreli alanları HAM olarak dışa
      aktarıyordu (Ayarlar'daki doğru çözülmüş export'un aksine) ve onu
      koruyacak bir yetkilendirme modeli hiç yoktu.
- [x] Doğrulama: 125/125 test yeşil (4 yeni güvenlik testi dahil — farklı
      tuzla farklı hash, yanlış PIN reddi, 128-bit tuz üretimi), gerçek
      SDL2 penceresinde ilk kurulum/yeniden giriş/yanlış PIN/sıfırlama
      akışları görsel doğrulandı, eski arka kapı/ekran taraması: 0 eşleşme.

## Bütçe Planlayıcı — kapsamlı güncelleme (2026-07-24, ayrı bir tur)

"Aylık Bütçe Planı" basit bir planlanan gelir/gider defterinden gerçek bir
bütçe TAKİP aracına dönüştürüldü: ay/yıl ayrımı, kategori bazlı
gerçekleşme takibi, sabit/değişken gider ayrımı, devreden bakiye, eşik
bazlı uyarı, otomatik öneri, şablon ve trend grafiği eklendi.

- [x] **Kritik gerçek bug düzeltildi**: `monthly_budget_plan` tablosunda
      `target_year` kolonu hiç yoktu; `calculate_monthly_budget` bir yıl
      parametresi alsa da sorgu yalnızca `target_month`'a göre
      filtreleniyordu — Ocak 2026 ile Ocak 2027 planı aynı kayıtlar
      olarak karışıyordu. `database/init_db.py:72` içine `target_year`
      eklendi, eski kayıtlar güncel yılla dolduruldu, tüm sorgular artık
      `WHERE target_month = ? AND target_year = ?` kullanıyor. Testte
      aynı ay için 2026/2027'ye farklı planlar yazılıp iki hesabın
      tamamen ayrı sonuç verdiği doğrulandı.
- [x] Şema ayrıca `category_name`, `rollover_enabled`, `is_template`,
      `alert_threshold_pct` kolonlarıyla genişletildi
      (`database/init_db.py:72`) — migration tekrar çalıştırılabilir ve
      geriye dönük uyumlu.
- [x] Kategori bazlı gerçek takip: plan kalemleri gerçek `categories`
      tablosuna aranabilir bir seçiciyle bağlanıyor ("Serbest metin gir"
      yolu da korunuyor), planlanan/gerçekleşen/yüzde/kalan
      `services/budget_service.py:40` içinde hesaplanıyor, şifreli
      tutarlar SQL'de değil Python'da çözülüyor. İlerleme çubukları
      yeşil/turuncu/kırmızı eşiklerle gösteriliyor
      (`mixins/budget_mixin.py:30`).
- [x] Sabit/değişken gider ayrımı: aktif abonelikler salt okunur sabit
      gider bölümünde, elle girilen kalemler ayrı "Planlanan Kalemler"
      bölümünde gösteriliyor.
- [x] Devreden bakiye/aşım: geçmiş kayıtlar geriye dönük değiştirilmeden,
      yalnızca bir önceki ayı kullanan zincirsiz devir mantığıyla
      hesaplama anında türetiliyor.
- [x] Otomatik öneri motoru: son üç tamamlanmış ayın ortalamasına göre
      "ÖNER" butonu tutar alanını arka plan thread'inde dolduruyor.
- [x] Şablon ("her ay otomatik tekrarla"): sorgu seviyesinde türetilen,
      belirli bir ayda düzenlenince yalnızca o ay için override oluşan,
      şablonun kendisini bozmayan bir mekanizma kuruldu.
- [x] Trend grafiği: son altı ayın planlanan/gerçekleşen serisini
      gösteren bir diyalog, bütçe kartına eklenen "Geçmiş / Trend"
      butonuyla açılıyor (`ui/dashboard.kv:738`).
- [x] Migration doğrulaması: gerçek veritabanı (`finance.db`, 380 KB,
      12 bütçe kaydı) değiştirilmeden önce yedeklendi
      (`db_backups/2026-07-24_budget_tracking/`), geçici bir kopya
      üzerinde migration çalıştırılıp 5 yeni kolonun eklendiği ve 12 eski
      kaydın `target_year=2026` ile backfill edildiği doğrulandı; kaynak
      veritabanına dokunulmadı.
- [x] Doğrulama: Bütçe servisi 7/7, tam paket **142/142** yeşil,
      `compileall`/`git diff --check` temiz. Gerçek SDL2/OpenGL
      penceresinde kategori arama, öneri motoru (200,00 TL), ilerleme
      yüzdeleri (%50/%85/%100 → yeşil/turuncu/kırmızı), salt okunur
      Netflix aboneliği, ilerleme çubuksuz "Acil Fon" serbest metin
      kalemi ve altı noktalı trend grafiği görsel doğrulandı. Daha önce
      de bilinen, zararsız tek bir `ResourceWarning: unclosed database`
      dışında sorun yok.

## Minimal Dashboard mimarisi + Abonelik Interceptor (2026-07-24, ayrı bir tur)

Ana sayfadaki büyük "Aylık Bütçe Planı" kartı, kullanıcının Araçlar
sekmesindeki diğer araçlarla (Hesap Makinesi, Faiz Getirisi, Bileşik Faiz vb.)
tutarlı, "Birikim Hedefi" gibi tıklanınca açılan minimal bir kart mimarisine
taşındı. Aynı turda kredi kartından geçen abonelik benzeri harcamaları
otomatik olarak "Aktif Aboneliklerim" radarına yazan bir interceptor kuruldu.

- [x] Bütçe planlayıcı `ui/dashboard.kv`'den çıkarılıp `ui/tools.kv` içinde
      `<BudgetPlannerPanel@MDCard>` olarak tanımlandı; ana sayfada yalnızca
      minimal `<BudgetSummaryCard@MDCard>` (`ui/dashboard.kv:904`,
      id: `budget_summary_card`) kaldı — "PLANLAYICIYI AÇ" ile panel açılıyor.
      Panelin kendi `ids` sözlüğü `root.ids`'ten ayrı tutuluyor
      (`mixins/budget_mixin.py`, bkz. `_planner_ids()` sözleşmesi).
- [x] Veri köprüsü: planlayıcıdaki değişiklikler (harcanan/limit) özet karta
      anında yansıyor; özet kartın tema bulunmayan unit-test ortamında hata
      vermesi ayrıca engellendi.
- [x] Abonelik interceptor'ı (`services/recurring_service.py`) — yalnızca
      kredi kartından geçen ve kategorisi abonelik (`SUBSCRIPTION_CATEGORIES`)
      olan veya tanınan bir marka adı içeren harcamalarda devreye giriyor;
      `register_subscription_from_transaction` idempotent şekilde
      `recurring_payments` tablosuna yazıyor (aynı isim varsa tekrar
      eklemiyor). Manuel "tekrarlanan ödeme" formuyla otomatik interceptor'ın
      çift kayıt oluşturması engellendi (interceptor yalnızca kredi kartı
      sinyaliyle çalışıyor).
- [x] Marka tanıma listesi bilinçli olarak boş bırakıldı:
      `services/recurring_service.py:40` — `KNOWN_BRANDS = []` — gerçek marka
      veri seti henüz doldurulmadı (aşağıda "Kalan İş" olarak işaretli).
- [x] PIN, hesap oluşturma ve işlem formlarında `write_tab=False` +
      `focus_next` ile TAB tuşu odak zinciri kuruldu; dinamik recurring
      alanları açılıp kapandığında zincir yeniden kuruluyor
      (`mixins/transaction_mixin.py:260-275`).
- [x] Bütçe formunun ağır yenilemeleri `Clock.schedule_once` ile farklı
      karelere dağıtılarak UI donması riski azaltıldı.
- [x] Doğrulama: `tests/test_budget_mixin.py`, `tests/test_subscription_
      interceptor.py` dahil tam paket **278/278** yeşil
      (`xvfb-run -a .venv/bin/python -m unittest discover -s tests`).

**Kalan iş (kasıtlı olarak bu turda yapılmadı, ayrı/hafif iş olarak
bırakıldı):**
- [ ] `services/recurring_service.py:40` — `KNOWN_BRANDS` listesinin gerçek
      marka veri setiyle (dijital platform, yazılım lisansı, bulut depolama,
      eğitim, spor, bağış, üyelik markaları) doldurulması.
- [ ] `BudgetSummaryCard`/`BudgetPlannerPanel` geçici metinlerinin ("Aylık
      Bütçe", "Bütçe planı hazırlanıyor...", "PLANLAYICIYI AÇ" vb.) TR/EN
      i18n karşılıklarının tamamlanması (`ui/i18n.py`).
- [ ] `ui/tools.kv` içindeki `<BudgetSummaryCard@MDCard>` ve
      `<BudgetPlannerPanel@MDCard>`'ın salt görsel cilası (renk/kontrast,
      padding/spacing, font boyutu, progress bar kalınlığı) — backend
      metotları ve widget ID'leri (`budget_planner_panel`,
      `budget_summary_card`, `budget_summary_text`, `budget_summary_bar`,
      `month_selector_container`, `projection_label`, `projection_icon`,
      `budget_detailed_list`) DEĞİŞMEDEN.

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
- [ ] Test paketinde zararsız ama tekrarlayan bir `ResourceWarning: unclosed
      database` var (2026-07-23 QA turunda görüldü) — test başarısızlığına
      yol açmıyor, ama bir yerde bağlantı `close()` edilmeden bırakılıyor
      olabilir; V1.0'ı bloklamıyor, gürültü olarak temizlenebilir.

## Sonraki Adım
Beş killer feature de (Madde 1-5) tamamlandı, isim/marka değişikliği
(Finora → Archlence) bitti, ikon üretildi. Paketleme öncesindeki esas
engeller (2026-07-23 denetim raporu): CI smoke testi, Python sürüm kararı,
sürüm/tag sistemi ve Linux paketleme altyapısının tamamı.

1. CI smoke testi ekle (Windows EXE'nin gerçekten açılıp çökmediğini
   doğrula) — düşük efor, yüksek güven.
2. Python sürüm kararı ver (3.12 mi 3.14 mü, ya da ikisi de test edilsin mi).
3. Git tag'e bağlı sürüm/adlandırma sistemi kur.
4. Linux paketleme altyapısını sıfırdan kur (`build-linux.yml`,
   `.desktop`, AppImage, platforma özgü spec ayarları).
5. Kalite takibindeki iki açık madde (insights widget render testleri,
   performans ölçümü) V1.0'ı bloklamıyor; paralel ya da sonrasında ele
   alınabilir.
