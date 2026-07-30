# Changelog

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
