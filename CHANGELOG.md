# Changelog

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
