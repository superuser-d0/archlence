# Changelog

## [0.0.2] — 2026-07-30

Windows'a özgü, veri kaybına yol açabilecek iki hata düzeltildi. Hâlâ bir
**ön yayımdır (pre-release)**.

### Öne çıkan değişiklikler

- Test paketi artık Windows'ta da CI'da koşuyor (daha önce yalnızca Linux'ta
  koşuyordu). Bu sürümdeki iki düzeltme doğrudan bu sayede bulundu.

### Finansal doğruluk ve güvenilirlik

- **Türkçe hata metni Windows'ta işlemi öldürebiliyordu.** Windows
  konsolu Türkçe kurulumlarda cp1252 kullanır ve bu kod sayfası 'ı', 'ğ',
  'ş' karakterlerini kodlayamaz. Uygulamanın hata mesajlarının çoğu
  `except` bloklarının içinde basıldığı için, kodlama hatası orada patladığında
  yakalanan istisna yutulmuyor, dışarı sızıp asıl işlemi öldürüyordu. Somut
  vaka: abonelik radarı bir işlem sırasında hata verdiğinde işlemin TAMAMI
  kayboluyordu. Konsol çıktısı artık UTF-8'e zorlanıyor; kodlanamayan
  karakterler '?' olur, süreç asla durmaz.
- **Tek-örnek kilidi Windows'ta kapanışta çökme riski taşıyordu.**
  Kilit dosyasının aynı baytı önce kilitleniyor sonra kırpılıyordu; Windows'un
  bayt-aralığı kilitleme API'si bu durumda kilidi bırakma çağrısında hata
  veriyor ve o hata yakalanmadığı için uygulama kapanışta çöküyordu. Kilit
  artık asla kırpılmayan sabit bir baytla çalışıyor ve kapanış her koşulda
  temiz tamamlanıyor.

### Performans

- `run_tests.py`, Windows'ta paketin tamamının alt süreç başına
  tekrar tekrar çalışmasına neden olan hatanın düzeltilmesiyle üç kata
  kadar daha hızlı: eskiden alt süreç açan her test tüm paketi o alt
  süreçte baştan çalıştırıyordu. Ölçüm CI görevi üzerindendir, kullanıcı
  makinesinde ayrıca doğrulanmamıştır.

### UI ve erişilebilirlik

Bu sürümde kullanıcıya görünen bir UI değişikliği yok; her iki düzeltme de
arka plan hata işleme ve süreç yaşam döngüsüyle ilgilidir.

### Test ve paketleme

- Test paketi artık Windows'ta CI'da koşuyor (daha önce yalnızca Linux'ta
  koşuyordu). Bu sürümdeki iki düzeltme doğrudan bu sayede bulundu.
- `run_tests.py` artık Windows'ta `multiprocessing`in `spawn` başlatma
  yöntemiyle güvenli: eskiden alt süreç açan her test, paketin tamamını
  o alt süreçte baştan çalıştırıyordu (Windows CI günlüğünde "Ran 599 tests"
  üç kez görünüyordu).
- Test izolasyonu Windows'ta gerçekten çalışır hale getirildi: testler
  artık platformdan bağımsız bir ortam değişkeniyle (`ARCHLENCE_HOME`)
  geçici bir dizine yönlendiriliyor. Daha önce kullanılan yöntem
  Windows'ta sessizce hiçbir şey yapmıyordu; testler gerçek kullanıcı
  profiline yazabiliyordu.
- v0.0.1 → v0.0.2 yükseltme smoke testi ilk kez gerçek bir taban sürümle
  çalışıyor: önceki sürüm kurulur, profile bir sentinel kayıt eklenir, yeni
  sürüm üzerine kurulur ve verinin bozulmadan korunduğu doğrulanır.

### Çalışma sırasında bulunup düzeltilen ek sorunlar

- Test paketindeki birkaç yardımcı fonksiyon SQLite bağlantılarını açık
  bırakıyordu (`with sqlite3.connect(...)` bağlantıyı kapatmaz, yalnızca
  bir transaction bloğudur). Linux'ta görünmüyordu çünkü açık bir dosya
  yine de silinebiliyor; Windows dosyayı kilitli tuttuğu için testler
  temizlik aşamasında başarısız oluyordu. Kapatma çağrıları eklendi.

### Bilinen sınırlamalar

- Hâlâ kararlı değildir; ön yayımdır.
- v0.0.1 → v0.0.2 yükseltme testi bu sürümde otomatikleştirildi; sonraki
  sürümden itibaren gerçekten çalışacak.
- Paketler imzasızdır; Windows SmartScreen uyarısı görülebilir.
- Fiyat servisi tek sağlayıcılıdır.
- Legacy CBC okuma eski profiller/backup'lar için deprecated olarak kalır.
- UI katmanındaki geniş exception/`print()` teknik borcu tamamen
  sıfırlanmadı.

### Kurulum ve checksum doğrulaması

- Windows: `ArchlenceSetup-0.0.2.exe`
- Linux: `Archlence-0.0.2-x86_64.AppImage`
- İndirme sonrasında aynı dizindeki `SHA256SUMS.txt` için
  `sha256sum -c SHA256SUMS.txt` çalıştırın. SBOM
  `Archlence-0.0.2-sbom.cdx.json` adıyla yayımlanır.

## [0.0.1] — 2026-07-30

İlk genel yayım. Bu sürüm bir **ön yayımdır (pre-release)**: paket kurulup
çalışıyor ve aşağıdaki akışlar test ediliyor, ancak kararlı sayılmaz ve
gündelik finans takibi için henüz önerilmez. Bilinen sınırlamalar bölümünü
okumadan kullanmayın.

### Öne çıkan değişiklikler

- Tutar alanına yazarken rakamların karışmasına yol açan imleç hatası
  düzeltildi (girilen tutar artık birebir korunuyor).
- Takvim, aylık bütçe, kategori ayarları ve işlem ekleme akışlarındaki
  donma/kasma nedenleri kaldırıldı.
- Varlık alımının hangi hesaptan karşılanacağı düzeltildi; "Yetersiz Bakiye"
  hatasıyla varlık eklenememesi sorunu giderildi.

### Finansal doğruluk ve güvenilirlik

- **Tutar girişi bozulması:** binlik ayraç maskesi Kivy'nin `on_text`
  olayında çalıştığı için imleç bir karakter geride kalıyor, sonraki hane
  yanlış konuma giriyordu. Yazılan `1234567` alana `1.235.674` olarak
  giriyordu — yani kullanıcı doğru rakamı yazdığı hâlde hesaba başka bir
  tutar kaydediliyordu. Maskeleme artık düzenleme tamamlandıktan sonra
  çalışıyor; gerçek bir SDL2/OpenGL penceresinde ölçülerek doğrulandı.
- **Absürt tutar koruması:** tam kısım 12 haneyle sınırlandı. Üzerindeki
  değerler `float64`'ün tam sayı kesinlik sınırını (2^53) aşıyor ve bakiye
  aritmetiğini sessizce bozuyordu. Sınır giriş anında uygulanır; mevcut
  kayıtlar etkilenmez.
- **Varlık alımı hesap seçimi:** alım koşulsuz `DEFAULT_ACCOUNT_ID` (=1)
  hesabından düşülüyordu. Uygulama artık varsayılan hesap oluşturmadığı için
  o satır hiç bulunmayabiliyor, ya da kullanıcının parası başka hesapta
  olabiliyordu; her iki durumda da her varlık alımı "Yetersiz Bakiye" ile
  reddediliyordu. Artık tutarı karşılayabilen vadesiz hesap seçilir, hiçbiri
  yetmiyorsa mesaj eksik tutarı ve hesabı adıyla söyler.
- **Geçmişe dönük işlem ekleme kaldırıldı:** geçmiş tarihli kayıt bakiyeyi
  anında değiştiriyor ama bakiye defterinde geriye dönük doğru yere
  oturmuyordu. İleri tarihli (bekleyen) işlem akışı korunmuştur.

### Performans

Aşağıdakilerin tamamı çağrı sayımıyla ölçülmüş ve regresyon testine
bağlanmıştır; süre ölçümü değil, iş miktarı ölçümüdür.

- **Takvim:** her gün dokunuşu 42 hücrelik ızgaranın tamamını yeniden kuruyor
  ve sınırsız iş parçacığı + SQLite bağlantısı açıyordu. Artık yalnız
  etkilenen iki hücre yeniden boyanıyor; 12 hızlı dokunuş 12 yerine **1**
  veritabanı okuması açıyor.
- **Aylık bütçe:** her ay butonu tam liste yeniden inşası tetikliyordu;
  12 hızlı geçiş artık **1** yeniden inşaya iniyor.
- **Kategori ayarları:** her anahtar dokunuşu tam grafik yeniden çizimi
  tetikliyordu; 10 hızlı dokunuş artık **1** tazelemeye iniyor.
- **İşlem ekleme:** dört ağır tazeleme tek karede çalışıyordu; her biri artık
  kendi karesinde çalışıyor, tek kare bloklanmıyor.

### UI ve erişilebilirlik

- Varlık eklenemediğinde genel "Varlık eklenirken hata oluştu!" yerine
  gerçek sebep gösteriliyor (ör. yetersiz bakiye ve eksik tutar).
- İşlem tarihi seçicisi geçmiş tarihleri artık hiç göstermiyor.

### Test ve paketleme

- **Test raporlaması onarıldı.** Kivy `import kivy` sırasında `sys.stderr`i
  kendi günlükleyicisine yönlendiriyor; test koşucusu akışı o noktadan
  aldığı için ~69. testten sonraki tüm çıktı kayboluyordu — kalan ~505
  testin adı, hata mesajları, yığın izleri ve `Ran N tests` / `OK|FAILED`
  özeti dahil. Çıkış kodu doğru kalıyordu, ancak günlüğe bakan hiç kimse
  neyin başarısız olduğunu göremiyordu. Gerçek akış artık her türlü Kivy
  içe aktarımından önce yakalanıyor.
- Fiyat/portföy hata yolları `print()` yerine kalıcı dönen günlük dosyasına
  yazıyor. Paket `console=False` ile derlendiği için bu mesajlar Windows'ta
  tamamen kayboluyordu.
- Test paketi: 595 test, tamamı geçiyor (bu sürümde 26 yeni regresyon testi).

### Çalışma sırasında bulunup düzeltilen ek sorunlar

- `tests/test_formatters.py`'deki sahte metin alanı Kivy'yi ters modelliyordu
  (imleci metinden önce güncelliyordu) ve bu yüzden imleç testleri, üretimde
  tutarı bozan hatayı yeşil gösteriyordu. Sahte, gerçek `insert_text`
  sıralamasına çekildi.
- `tests/test_asset_price_worker.py` `print()` çağrısını gözleyerek
  "loglandı" doğruluyordu; paketlenmiş uygulamada bu "kayboldu" anlamına
  geliyordu. Test gerçek günlükleyiciyi doğrulayacak şekilde güncellendi.

### Bilinen sınırlamalar

- **Kararlı değildir.** Ön yayımdır; günlük finans takibi için önerilmez.
- Windows'ta altın/varlık ekleme düzeltmesi kullanıcı tarafından doğrulanmayı
  bekliyor. Bir hata olursa günlük dosyası artık gerçek sebebi içerir:
  `%LOCALAPPDATA%\Archlence\Archlence\Logs\archlence.log`
- Paketler imzasızdır; Windows SmartScreen uyarısı görülebilir.
- Fiyat servisi tek sağlayıcılıdır.
- Legacy CBC okuma eski profiller/backup'lar için deprecated olarak kalır.
- UI katmanındaki geniş exception/`print()` teknik borcu tamamen
  sıfırlanmadı.
- Finansal `Decimal` kuralları tanımlı, ancak tüm para yolları henüz
  `Decimal` tabanlı değildir.

### Kurulum ve checksum doğrulaması

- Windows: `ArchlenceSetup-0.0.1.exe`
- Linux: `Archlence-0.0.1-x86_64.AppImage`
- İndirme sonrasında aynı dizindeki `SHA256SUMS.txt` için
  `sha256sum -c SHA256SUMS.txt` çalıştırın. SBOM
  `Archlence-0.0.1-sbom.cdx.json` adıyla yayımlanır.
