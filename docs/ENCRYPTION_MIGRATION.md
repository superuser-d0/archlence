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
örneği çalışmamalıdır. Single-instance kilidi tamamlanmadan migration akışı
stable üretim sürümünde etkinleştirilmemelidir.
