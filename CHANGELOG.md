# Changelog

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
