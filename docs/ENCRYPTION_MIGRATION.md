# Legacy şifreleme migration'ı

Archlence yeni kayıtları `AEADv1` (AES-256-GCM) biçiminde üretir. Eski
kurulumlardan kalan AES-CBC kayıtları okunabilir, fakat bütünlük doğrulaması
taşımadıkları için kontrollü olarak yeni biçime geçirilmelidir.

Migration otomatik ve habersiz başlatılmaz. Önce salt-okunur envanter
çalıştırılarak taşınacak alan ve etkilenen kayıt sayısı kullanıcıya
gösterilmelidir. Kullanıcı ayrıca backup hedefini ve anahtar kaybının veriyi
okunamaz hâle getireceğini görmelidir.

Uygulanan güvenlik sırası:

1. Mevcut DB ve anahtarın eşleştiği, parola korumalı ve doğrulanmış backup
   oluşturulur.
2. Veritabanı `BEGIN IMMEDIATE` transaction'ı ile kilitlenir.
3. Her legacy alan çözülür, AEAD ile yeniden şifrelenir ve tekrar çözülerek
   doğrulanır.
4. Bütün alanlar başarıyla taşındıysa migration kaydı ve veriler birlikte
   commit edilir.
5. Herhangi bir hata bütün transaction'ı geri alır; doğrulanmış backup
   korunur.

Aynı migration yeniden çalıştırılabilir. `AEADv1:` alanlar atlanır; legacy
alan kalmadığında DB veya backup dosyası değiştirilmez.

Migration sırasında aynı kullanıcı profilini kullanan ikinci Archlence
örneği çalışamaz; single-instance kilidi migration'dan önce alınır.

## Legacy okuma yolunun kaldırılma koşulları

CBC okuma desteği yeni veri yazamaz, deprecated ve yalnız migration/restore
uyumluluğu için izole edilmiştir. Aşağıdaki koşulların tamamı sağlanmadan
kaldırılmayacaktır:

1. Desteklenen tüm profillerde envanter sıfır legacy alan raporlar.
2. v1.0.x backup'ları güncel sürümde restore edilip kontrollü migration'dan
   geçirilebilir.
3. En az bir tam kararlı sürüm boyunca migration telemetrisi yerine
   kullanıcının yerel envanter ekranı sıfır kayıt gösterir.
4. Backup saklama politikası ve son legacy-okuyabilen sürüm açıkça belgelenir.

Bu koşullar sağlanana kadar `_decrypt_legacy_cbc` yalnız geriye dönük okuma
testleriyle korunur; yeni yazım yalnız `AEADv1` üretir.
