# Security and reliability status

Bu belge v1.1.0 kaynak ağacının tek güncel güvenlik ve güvenilirlik özetidir.
Tarihli audit belgeleri yalnız kendi commit'lerinin arşivlenmiş baseline'ıdır.

## Stable ne anlama gelir?

- Paket ve kullanım kararlılığı: Windows installer ve Linux AppImage CI'da
  gerçek açılış smoke testlerinden geçer; Windows akışı kurulum ve kaldırmayı
  da doğrular.
- Finansal doğruluk: dashboard dönem/30-gün metrikleri ile bütçe toplamları
  bozuk şifreli kaydı sıfır saymaz. Ortak Decimal politikası fiat, miktar ve
  yüzde sınırlarını tanımlar.
- Veri koruma: yeni hassas veri yalnız AEAD ile yazılır. Backup DB ve parola
  korumalı kurtarma anahtarını birlikte doğrular; restore rollback-safe'dir.
- Stable, bankacılık veya muhasebe sertifikası anlamına gelmez. Fiyat verileri
  üçüncü taraf sağlayıcıdan gelir ve kaynak/yaş/güncellik durumu taşır.

## Bilinen sınırlamalar

- Legacy CBC okuma yolu eski profil ve backup uyumluluğu için deprecated
  biçimde kalır. Yeni veri bu formatta yazılamaz.
- Fiyat servisi tek sağlayıcılıdır (Yahoo Finance). İkinci adapter v1.2.0
  planındadır; çok eski cache kesin güncel değer olarak sunulmaz.
- UI mixin'lerinde kalan geniş exception ve `print()` borcu sıfır değildir;
  CI yeni geniş/sessiz handler eklenmesini engeller ve baseline azaltılır.
- Paketler kod imzalı değildir. Windows SmartScreen uyarısı görülebilir;
  AppImage da kriptografik olarak imzalanmamıştır. SHA-256 ve SBOM yayımlanır.
