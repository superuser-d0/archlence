# Changelog

## [0.0.1] — 2026-07-30

Bu sürüm bir **ön yayımdır (pre-release)**. Sürüm numarası bilerek 0.0.x'e
çekildi: önceki 1.x etiketleri, kullanıcı testinde ortaya çıkan ve gündelik
kullanımı bozan hatalar nedeniyle geri çekildi. Kararlı sayılmaz.

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

## [1.1.0] — 2026-07-30

### Öne çıkan değişiklikler

- Dashboard ve bütçe hesaplarının finansal veri-kalitesi sınırları
  merkezileştirildi.
- Fiyat sonuçlarına kaynak, son güncelleme, cache yaşı ve
  güncel/gecikmiş/kullanılamıyor durumu eklendi.

### Finansal doğruluk ve güvenilirlik

- Bozuk şifreli bütçe tutarını `0.0` sayan fail-open yol kaldırıldı; problemli
  tablo ve kayıt kimliğiyle tüm türetilmiş sonuç geçersiz kılınıyor.
- Dashboard dönemsel ve 30 günlük projeksiyon girdileri ortak fail-closed
  özet sözleşmesine geçirildi; bozuk kayıt artık sessizce dışlanmıyor.
- Fiat, altın, hisse, kripto ve yüzde için `Decimal` tabanlı ortak
  round-half-even kuralları tanımlandı ve test edildi.
- Legacy CBC yeni veri yazamıyor; kaldırılma koşulları ve eski backup
  bağımlılığı belgelendi.

### Performans

- Bu sürüm için henüz baseline'a göre ölçülmüş bir hız artışı iddia edilmiyor.
  Karşılaştırmalı sonuçlar release kalite koşuları tamamlandığında raporlanır.

### UI ve erişilebilirlik

- Arama alanı ve varlık dialoglarının tema, focus, pencere boyutu, Türkçe/
  İngilizce ve 1×/2× DPI sözleşmeleri gerçek Xvfb/SDL CI matrisine bağlandı.

### Test ve paketleme

- Finansal Decimal, bozuk bütçe kaydı, metrik kalite durumu ve fiyat cache
  güncelliği için regresyon testleri eklendi.
- Domain type-check kapsamı model, finansal servis, backup/migration, bütçe
  ve fiyat servislerine genişletildi.
- CycloneDX SBOM release asset'i eklendi; release notları doğrudan bu
  CHANGELOG bölümünden üretiliyor.

### Çalışma sırasında bulunup düzeltilen ek sorunlar

- Stable-readiness ve exception audit belgelerinin güncel durum sanılmasını
  önlemek için arşiv uyarıları eklendi.
- Backup/recovery belgelerindeki tamamlanmış single-instance işini hâlâ eksik
  gösteren metin düzeltildi.

### Bilinen sınırlamalar

- Paketler imzasızdır; Windows SmartScreen uyarısı görülebilir.
- Fiyat servisi v1.1.0'da tek sağlayıcılıdır. İkinci adapter v1.2.0 planıdır.
- Legacy CBC okuma eski profiller/backup'lar için deprecated olarak kalır.
- UI katmanındaki geniş exception/`print()` teknik borcu tamamen sıfırlanmadı.

### Kurulum ve checksum doğrulaması

- Windows: `ArchlenceSetup-1.1.0.exe`
- Linux: `Archlence-1.1.0-x86_64.AppImage`
- İndirme sonrasında aynı dizindeki `SHA256SUMS.txt` için
  `sha256sum -c SHA256SUMS.txt` çalıştırın. SBOM
  `Archlence-1.1.0-sbom.cdx.json` adıyla yayımlanır.

## [1.0.1] — 2026-07-30

- Varlık alımı, karşılık gelen hesap işlemi, bakiye değişimi ve ledger olayı
  tek SQLite transaction içinde atomik hale getirildi.
- Başarılı DB kaydından sonraki UI yenileme hataları artık yanlış kayıt-hatası
  mesajı üretmiyor.
- Yeni varlık liste ve portföy özetlerinde otomatik görünüyor; bayat arka plan
  sonucu yeni listeyi ezemiyor.
- Hızlı çift gönderim tek satın alma göreviyle birleştiriliyor.
- Altın ekleme ve BIST seçim dialogları küçük pencerelerde başlık, içerik ve
  aksiyon satırı çakışmayacak şekilde responsive hale getirildi.

## [1.0.0] — 2026-07-30

- Şifreleme ve finansal toplamlar fail-closed hâle getirildi.
- AEAD bütünlük doğrulaması, kontrollü legacy migration ve rollback eklendi.
- Parola korumalı, DB/anahtar eşleşmesi doğrulanan backup/restore eklendi.
- Windows DPAPI ve Linux Secret Service/KWallet anahtar depoları eklendi;
  güvenli depo yoksa dosya fallback’i kullanıcıya açıkça gösteriliyor.
- Anahtar kurtarma ve rollback’li anahtar rotasyonu eklendi.
- Aynı kullanıcı profili için ikinci uygulama örneği engellendi.
- Arama alanı ve pencere sağındaki render çizgileri kaldırıldı.
- Büyük veri benchmark’ı ve background-task yarış korumaları eklendi.
- Kritik lint, type-check ve exception-regresyon kontrolleri CI’da blocking
  hâle getirildi.
