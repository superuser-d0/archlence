# Backup ve kurtarma

Archlence backup paketi veritabanını, format metadata'sını ve parola ile
korunan kurtarma materyalini birlikte taşır. Ham `encryption.key` dosyası
pakete eklenmez.

## Güvenlik sözleşmesi

- Kurtarma parolası en az 12 karakterdir ve uygulama tarafından saklanmaz.
- Anahtar, PBKDF2-HMAC-SHA256 (600.000 tur) ile türetilen anahtarla
  AES-256-GCM kullanılarak korunur.
- Backup ancak SQLite `integrity_check`, dosya hash'i ve veritabanındaki tüm
  AEAD alanların anahtarla doğrulanması başarılıysa tamamlanır.
- Restore başlamadan önce mevcut verinin ayrıca doğrulanmış güvenlik backup'ı
  alınır.
- Restore sırasında hata oluşursa veritabanı ve anahtar önceki hâline geri
  taşınır.

## Kullanıcının saklaması gerekenler

Backup paketi ve kurtarma parolası birbirinden ayrı, güvenli yerlerde
saklanmalıdır. Parola kaybolursa paketteki anahtar açılamaz; Archlence veya
proje geliştiricileri veriyi kurtaramaz. Yalnız `finance.db` dosyasını
kopyalamak yeterli değildir; onu açan şifreleme anahtarı da gereklidir.

## Restore işlemi

Restore yalnız doğrulama tamamlandıktan sonra yapılır. Hedefte mevcut veri
varsa `pre-restore-YYYYMMDD-HHMMSS.archlence-backup` biçiminde güvenlik
backup'ı üretilir. Gelen paketin parolası yanlışsa, DB hash'i bozuksa veya
anahtar şifreli kayıtlarla eşleşmiyorsa hedef dosyalara dokunulmaz.

Backup ve restore sırasında uygulamanın başka bir örneği aynı kullanıcı
profilini kullanmamalıdır. Single-instance koruması stable kalite kapısının
ayrı bir maddesidir; bu koruma tamamlanana kadar bu özellik üretim için hazır
ilan edilmez.
