# Anahtar yönetimi

Archlence her kurulum için rastgele 256 bit AES anahtarı kullanır.

## Platform koruması

- Windows: anahtar, mevcut Windows kullanıcısına bağlı DPAPI ile korunmuş
  blob olarak kullanıcı veri dizininde tutulur.
- Linux: kullanılabilir bir Secret Service veya KWallet backend'i varsa
  Python `keyring` arayüzü kullanılır.
- OS deposu yoksa 0600 izinli yerel dosya fallback'i kullanılır. Bu durum
  sessiz değildir; Ayarlar ekranı kullanılan yöntemi ve uyarıyı gösterir.

Eski `encryption.key` dosyası bulunduğunda anahtar önce OS deposuna yazılır,
geri okunup doğrulanır ve ancak bundan sonra eski dosya
silinir. Böylece OS deposuna geçişten sonra diskte ikinci bir ham anahtar
kopyası bırakılmaz.

## Kurtarma paketi

Ham anahtar dışa aktarılmaz. Kurtarma paketi anahtarı en az 12 karakterli
paroladan PBKDF2-HMAC-SHA256 ile türetilen anahtarla AES-256-GCM kullanarak
korur. Paket ve parola ayrı yerlerde saklanmalıdır. Parola kaybolursa paket
açılamaz.

İçe aktarma sırasında kurtarılan anahtar önce veritabanındaki bütün AEAD
alanlarla doğrulanır. Eşleşmeyen anahtar aktif anahtarın üzerine yazılmaz.

## Anahtar rotasyonu

Rotasyon önce doğrulanmış backup oluşturur. Veritabanının geçici bir kopyası
eski anahtarla çözülüp yeni anahtarla şifrelenir ve doğrulanır. Yeni anahtar
ile staged veritabanı birlikte devreye alınır. Dosya değişimi başarısız olursa
eski DB ve eski anahtar geri yüklenir.

Rotasyon çağrısı mevcut anahtar parmak izini ve benzersiz rotasyon kimliğini
taşır. Bayat veya yanlışlıkla yinelenen istek reddedilir. Legacy CBC alan
varsa önce legacy migration tamamlanmalıdır.

Bir saldırgan kullanıcının açık oturumuna ve çalışmakta olan Archlence
sürecine tamamen hâkimse OS key store tek başına koruma sağlayamaz. Bu model
özellikle diskten anahtar kopyalama ve başka kullanıcı hesabından erişim
riskini azaltır; işletim sistemi hesabının ele geçirilmesini çözmez.
