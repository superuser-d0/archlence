# Birikim hedefleri: SQLite'ı tek doğruluk kaynağı yapma planı

**Durum: KARARLAR VERİLDİ — UYGULANIYOR.**

Bu belge canlı finansal veriye dokunan bir şema göçünü tarif eder. Buradaki her
iddia mevcut kod okunarak ya da ölçülerek üretildi; varsayım kullanılmadı.
Taslaktaki açık ürün kararları kapatıldı ve gerekçeleri §0'a yazıldı.

---

## 0. Verilen kararlar (özet)

| Konu | Karar | Gerekçe |
|---|---|---|
| Şema kuşağı | `SCHEMA_VERSION` 1 → 2 | Eski sürüm yeni DB'yi bayat JSON'la birlikte yorumlarsa kusur geri gelir; fail-closed reddetme tercih edildi |
| Kalıcı kimlik | `goal_uid` = UUIDv4; sayısal `id` iç anahtar olarak KALIR | `balance_events.entity_id` sayısal id'ye bağlı; defteri kırmadan kimlik kalıcılaştırılıyor |
| `created_at` / `color` | Taşınır | Kullanıcı görünür veri |
| `auto_deposit` | Taşınır, varsayılan `0` (false) | Bugün davranışa bağlı değil ama kullanıcının oluşturduğu bir tercih; sessizce düşürmek veri kaybıdır. Kaldırma ayrı bir ürün kararıdır |
| Belirsiz kayıt | Karantina; otomatik eşleştirme ve silme YOK | Ad+tutar benzerliği kimlik kanıtı değildir |
| Finansal tutar | Göç hiçbir bakiyeyi, `current_amount`/`target_amount` değerini ve `balance_events` satırını DEĞİŞTİRMEZ | Defter SQL'de; JSON türev veridir |
| Karantina bildirimi | Açılışta tek seferlik diyalog, kalıcı kayıtla | Sessiz log, düzeltmeye çalıştığımız kusurun sessiz hâli olurdu |
| `.migrated` dosyası | Süresiz korunur, kullanıcı veri dizininde | Otomatik veri silme bu planın ilkeleriyle çelişir |

---

## 1. Mevcut veri akışı ve kök neden

### Ölçülen akış

```
AÇILIŞ   main.py:511   JsonStore(savings_goals.json) -> self.savings_goals
ÇİZİM    savings_mixin.render_savings_goals  <- self.savings_goals   (JSON)
PARA     savings_mixin._do_add
            1. SavingsService.deposit_to_goal(goal_id, ...)   -> SQL COMMIT
            2. self.store.put('goals', ...)                   -> JSON yazımı
BACKUP   backup_service.create_backup
            üyeler: finance.db, metadata.json, key.recovery.json [, config.json]
            savings_goals.json  YOK
```

**Görüntü JSON'dan, para SQL'den** geliyor ve yedek yalnız SQL'i taşıyor.

### Kök neden ikiye ayrılıyor

**(a) Yedek kapsamı.** `savings_goals.json` pakete girmiyor. Boş profile
restore edildiğinde SQL'de hedef var, arayüzde yok.

**(b) Kimlik yeniden kullanımı — asıl tehlike.** `sqlite_sequence` tablosu
`finance.db` dosyasının İÇİNDE. Restore dosyayı bütün olarak değiştirdiği için
sayaç da yedekteki değere geri dönüyor. Restore'dan sonra oluşturulan hedef,
bayat JSON'un hâlâ işaret ettiği id'yi yeniden alıyor. Ölçüldü
(`tests/test_savings_identity_reuse_regression.py`, dilim 0):

```
2) backup alindi           | sqlite_sequence = 1
3) backup SONRASI hedef id : 2 | sqlite_sequence = 2
4) restore sonrasi         | sqlite_sequence = 1   <-- sayac geri dondu
5) restore SONRASI yeni id : 2 | CAKISMA: True
6) bayat id'ye yatirim     : KABUL EDILDI
7) hesap bakiyesi          : 5000.0 -> 4750.0
   PARA: [(1,'Araba Fonu',0.0), (2,'Yeni Hedef',250.0)]
```

Kullanıcı "Tatil Fonu"nu fonladığını sanıyor; para "Yeni Hedef"e yazılıyor.
**Sessiz yanlış atıf — bu planın var oluş sebebi.**

### Neyin bozulmadığı (kapsamı doğru çizmek için)

JSON'daki tek kullanıcı verisi birikim hedefleridir. Hesaplar, işlemler,
borçlar, varlıklar, düzenli ödemeler tamamen SQLite'ta ve restore'dan sorunsuz
geçiyor. `config.json` ayar verisidir ve zaten (opsiyonel) yedekleniyor.

---

## 2. Hedef şema

### 2.1 Eklenecek sütunlar

| Sütun | Tip | Gerekçe |
|---|---|---|
| `goal_uid` | `TEXT` (sonunda `NOT NULL`, `UNIQUE`) | Nesiller arası kalıcı kimlik (§3) |
| `color` | `TEXT NULL` | JSON'da var, SQL'de yok. Kullanıcı görünür veri |
| `auto_deposit` | `INTEGER NOT NULL DEFAULT 0` | Kullanıcı tercihi; varsayılan false |
| `created_at` | `TEXT NULL` | ISO-8601; sıralama ve ayniyet tartışmasında kanıt |

Mevcut sütunlar (`id`, `goal_name`, `target_amount`, `current_amount`,
`target_date`, `status`) **değişmiyor**.

Sütun SIRASI hem taze `CREATE TABLE` hem de göç eden profilin `ALTER TABLE`
zincirinde AYNIDIR. `scripts/audit/check_schema_consistency.py` taze ve göç
etmiş şemayı sütun sütun karşılaştırıyor; sıra farkı kapıyı kırardı.

### 2.2 Sayısal `id` KALIYOR

`balance_events.entity_id` sayısal `goal_id` tutuyor ve geçmiş defter satırları
bu değere bağlı (`record_balance_event(cursor, SAVINGS_GOAL, goal_id, ...)`).
`id`'yi kaldırmak defteri kırardı. `id` **iç birincil anahtar** olarak kalır;
kalıcı kimlik `goal_uid`'dir. Hiçbir eşleştirme YALNIZ `id` üzerinden yapılmaz.

### 2.3 Kısıtların aşamalı uygulanması

`goal_uid` üzerinde `UNIQUE` **evet**, `NOT NULL` **hemen değil**:

1. Dilim 1: sütun `NULL` kabul ederek eklenir, `UNIQUE` index kurulur
   (SQLite `UNIQUE` birden çok `NULL`'a izin verir).
2. Aynı dilimde backfill tüm mevcut satırları bir defalık `uuid4()` ile
   doldurur. Backfill YALNIZ `goal_uid IS NULL` satırlara yazar; ikinci koşumda
   var olan hiçbir UID değişmez.
3. Dilim 5, backfill'in eksiksiz olduğu doğrulandıktan **sonra** `NOT NULL`'u
   tablo yeniden yaratımıyla uygular.

`NOT NULL`'u backfill'den önce koymak, göç yarıda kalırsa açılmayan bir
veritabanı bırakırdı.

**Tablo yeniden yaratımı ve taze kurulum:** taze `CREATE TABLE` `goal_uid`'i
doğrudan `NOT NULL` tanımlar; göç eden profil ise yeniden yaratımla aynı
tanıma ulaşır. İki yol yapısal olarak AYNI şemada buluşur — aksi hâlde
`check_schema_consistency` "fresh vs upgraded" karşılaştırması kırılırdı.
Yeniden yaratım `id` değerlerini KORUR (açık sütun listesiyle
`INSERT ... SELECT`), çünkü `balance_events` o değerlere bağlı.

### 2.4 Şema kuşağı

`SCHEMA_VERSION` 1 → 2. `init_db.py` hâlihazırda `found > SCHEMA_VERSION` ise
`SchemaTooNewError` fırlatıyor; §7 buna yaslanıyor.

### 2.5 Karantina tablosu

```
savings_migration_quarantine(
    id, quarantined_at, reason, source, legacy_id,
    goal_name(ŞİFRELİ), target_amount, current_amount,
    payload(ŞİFRELİ ham kayıt), acknowledged
)
```

- **Finansal toplamlara GİRMEZ.** Hiçbir metrik, defter ya da bakiye sorgusu bu
  tabloyu okumaz; buradan para hareketi başlatılamaz.
- `goal_name` ve `payload` kişisel finans verisidir, `savings_goals.goal_name`
  ile aynı AEAD yoluyla şifrelenir ve `backup_service.ENCRYPTED_FIELDS`'e
  eklenir — böylece yedek doğrulaması bu satırları da anahtara karşı sınar.
- Tablo `finance.db` içinde olduğu için yedek/restore kapsamına
  KENDİLİĞİNDEN girer; ayrı bir dosya formatı icat edilmez.

### 2.6 Göç işareti (provenance) tablosu

```
savings_migration_state(marker TEXT PRIMARY KEY, completed_at TEXT, detail TEXT)
```

**Bu tablo taslak planda YOKTU ve eklenmesi zorunlu bir düzeltmedir.** Taslak,
"gerçek legacy profil" ile "restore sonrasında ortada kalmış bayat JSON"
ayrımını nasıl yapacağını söylemiyordu; ikisi diskte aynı görünüyor.

İşaret `finance.db`'nin İÇİNDE durur, yani DB generation'ıyla birlikte
hareket eder. Kural:

| DB'de işaret | Diskte `savings_goals.json` | Karar |
|---|---|---|
| yok | var | **Gerçek legacy profil** → göç et |
| var | var | **Bayat JSON** → göç ETME, karantinaya al, kullanıcıya bildir |
| var/yok | yok | Yapılacak bir şey yok |

Bu ayrım güvenilir çünkü işaret ile veritabanı satırları AYNI dosyada ve aynı
restore generation'ında taşınıyor. Ayrımı yapamadığımız bir hâl kalırsa kayıt
karantinaya alınır.

---

## 3. Kimlik stratejisi

### Karar: `goal_uid` (UUIDv4, metin)

Sayısal `id` kalıcı kimlik olarak **kullanılamaz** — §1(b) bunu ölçtü.
`AUTOINCREMENT` garantisi restore'u aşmıyor, çünkü sayaç da yedeğin parçası.

### Backfill

Dilim 1'de her mevcut satıra `uuid4()` yazılır ve o satırın ömrü boyunca
değişmez. Deterministik türetme (ör. ad+tutar hash'i) BİLEREK kullanılmadı:
aynı ad ve tutara sahip iki meşru hedef aynı UID'yi alır, `UNIQUE` kısıtı
göçü kilitler ve "belirsizlikte otomatik karar verme" ilkesi çiğnenirdi.

### JSON kayıtlarıyla ilişkilendirme

JSON'da `goal_uid` hiç olmadı. İlk göçte eşleştirme §6'daki karar tablosuyla
yapılır ve **`id` tek başına yeterli kanıt sayılmaz**.

### Servis sınırında fail-closed doğrulama

`deposit_to_goal`, `withdraw_from_goal` ve `delete_goal` **opsiyonel bir
`goal_uid` parametresi alır** (taslak planda "imzalar değişmez" yazıyordu; bu
yanlıştı — UI'ın hangi hedefi kastettiğini kanıtlayabilmesi için gerekli).
Verilirse `WHERE id = ? AND goal_uid = ?` uygulanır; eşleşmezse işlem
**reddedilir**, para hareket etmez. Arayüz her zaman UID geçirir; UID taşımayan
bir kart kaydı (ör. bayat JSON'dan gelen) fail-closed reddedilir.

### Restore davranışı

`goal_uid` veritabanının içinde olduğu için yedekle taşınır ve doğru satıra
geri gelir. `sqlite_sequence` geri sarsa bile UID değişmez; restore sonrası
oluşturulan hedef **yeni bir UID** alır. Kimlik yeniden kullanımı yapısal
olarak imkânsızlaşır.

---

## 4. Göç durum makinesi ve transaction sınırları

### Tetikleme

Göç açılışta, `initialize_database()` sonrası ve arayüz hedefleri okumadan
ÖNCE çalışır. Eşzamanlı ikinci örnek tek örnek kilidiyle zaten engelleniyor.

### Durumlar

```
YOK         JSON yok ya da işaret zaten var  -> hiçbir şey yapma
OKUNDU      JSON parse edildi                -> sınıflandır (§6)
PLANLANDI   her kayıt bir karara bağlandı
UYGULANDI   tek transaction commit edildi
DOĞRULANDI  §8 doğrulamaları geçti
EMEKLİ      JSON .migrated-<ISO>'ya taşındı, işaret yazıldı
```

Her durum `.archlence-savings-migration/journal.json` dosyasına atomik yazılır
(restore journal'ının deseninin aynısı: geçici dosya + `os.replace` + `fsync`).

### Transaction sınırı

**Tüm SQL yazımları TEK transaction:**

```
BEGIN IMMEDIATE
  eksik hedefleri INSERT et (goal_uid ile)
  eşleşen hedeflerin YALNIZ boş alanlarını UPDATE et (color/auto_deposit/created_at)
  belirsiz kayıtları karantinaya INSERT et
COMMIT
```

`BEGIN IMMEDIATE` seçiliyor çünkü yazma kilidini baştan almak commit anındaki
çakışmayı önler.

### Yarıda kalma

Commit olmadıysa SQLite geri alır, JSON dokunulmamıştır, göç bir sonraki
açılışta baştan çalışır. Commit olduysa ama doğrulama/emeklilik yarıda
kaldıysa journal `UYGULANDI`'da kalır ve sonraki açılış kaldığı yerden devam
eder; INSERT'ler idempotent olduğu için tekrar satır üretmez. **İşaret yalnız
başarılı tamamlanmadan SONRA yazılır.**

### Finansal tutar üretmeme

Göç **hiçbir `balance_events` satırı yazmaz** ve hiçbir hesap bakiyesine
dokunmaz. Yalnız `savings_goals` ve karantina tablosuna yazar.
`current_amount` JSON'dan **yalnızca SQL'de karşılığı olmayan** hedefler için
alınır; eşleşen hedeflerde SQL değeri korunur.

Göçün eklediği hedef için `savings_goal_created` açılış çizgisi, `init_db`'nin
zaten var olan `_backfill_ledger_baseline` mekanizmasıyla bir sonraki açılışta
yazılır — göç defteri kendisi yazmaz, böylece göç adımında defter
değişmezleri sabit kalır ve doğrulama (§8.4) anlamlı olur.

---

## 5. Restore entegrasyonu ve rollback

### Tek generation

Restore, DB + anahtar + config + **yaşayan `savings_goals.json`**'u TEK
generation olarak değiştirir. Mevcut restore journal'ı GENİŞLETİLİR; paralel
ikinci bir journal icat EDİLMEZ.

- `old-savings_goals.json` journal dizinine kopyalanır.
- Restore başarılıysa dosya **karantinaya** alınır
  (`savings_goals.json.stale-<zaman>`), silinmez.
- Restore başarısızsa geri konur — DB, anahtar, config ve JSON aynı generation
  olarak döner.

### Yarıda kesilme

`recover_interrupted_restore()` zaten journal'dan toparlıyor; eklenen tek şey
`old-savings_goals.json`'u rollback yolunda geri koymak, COMMITTED yolunda ise
bayat JSON'un karantinaya alınmasını tamamlamak.

### Bellek durumu

Restore başarılı olduğunda `self.savings_goals` **SQL'den yeniden yüklenir**
(`SavingsService.get_goals()`) ve `render_savings_goals()` çağrılır.
**Yeniden başlatma gerekmez.**

### Eski backup formatları

Yedek paketinde JSON YOKTUR ve olmayacak; hedefler `finance.db` içinde
taşınıyor. Mevcut paketler (format_version 2) değişmeden desteklenmeye devam
eder — restore tarafına yeni bir zorunlu üye eklenmiyor. Yeni yedek, hedeflerin
bütün alanlarını ve karantina durumunu SQL üzerinden kapsar.

### Başka profile ait yedek

`goal_uid` UUIDv4 olduğundan profiller arası çakışma pratikte imkânsız. Restore
DB'yi bütün olarak değiştirdiği için karışım da oluşmaz; sayısal id çakışması
artık yanlış eşleşme üretemez, çünkü hiçbir eşleştirme yalnız id'ye bakmıyor.

---

## 6. Belirsiz/çakışmalı kayıt politikası

### Eşleştirme sırası

1. İşaret varsa göç HİÇ çalışmaz (bayat JSON kuralı, §2.6).
2. İlk göçte UID yok; aday eşleştirme **`(id, goal_name)` ÇİFTİ** ile yapılır.
   Yalnız ikisi de tutarsa eşleşme sayılır.
3. Hiçbiri tutmazsa kayıt yenidir ya da karantinadır.

### Karar tablosu

| Durum | Karar |
|---|---|
| JSON ve SQL tam eşleşiyor (`id` + `goal_name`) | Eşleştir. Yalnız BOŞ `color`/`auto_deposit`/`created_at` alanlarını doldur. **Tutarlara dokunma.** |
| JSON'daki `id` SQL'de yok | Yeni satır INSERT, yeni UID. `current_amount` JSON'dan |
| Aynı `id`, farklı isim | **KARANTİNA.** §1(b)'nin ürettiği tam durum |
| Aynı mantıksal hedef farklı `id`'lerle | **KARANTİNA.** Ad+tutar kanıt sayılmaz |
| SQL'de var, JSON'da yok | **Hiçbir şey yapma.** SQL zaten kaynak |
| JSON bozuk/kısmi | Göçü DURDUR, `.unreadable-<zaman>` karantina, kullanıcıya bildir. Kısmi göç YOK |
| Şifreleme anahtarı yok | Göç çalışmaz, işaret yazılmaz, JSON'a dokunulmaz; sonraki açılış tekrar dener |
| Aynı ad ve tutarda iki MEŞRU hedef | İkisi de kendi `id`'siyle eşleşir; ad+tutar sezgisi kullanılmadığı için yanlış pozitif yok |
| İşaret var, JSON hâlâ ortada | **KARANTİNA** (bayat JSON), göç YOK |

### Ad+tutar sezgisi neden REDDEDİLDİ

"Aynı ad + aynı tutar = aynı hedef" yanlış pozitif üretir: iki çocuğa aynı adla
açılmış ("Eğitim", 50.000) iki hedef meşrudur ve birleştirilirse biri kaybolur.
**Belirsizlikte otomatik karar verilmez.**

### Karantina yüzeyi

Karantina kayıtları `savings_migration_quarantine` tablosuna yazılır ve
açılışta **tek seferlik** diyalogla bildirilir (`acknowledged` işaretiyle).
Sessiz atma YOK — bu, düzeltmeye çalıştığımız kusurun sessiz hâli olurdu.
Karantina kaydı ne bir bakiyeye, ne bir toplama, ne de bir para hareketine
katılır; yalnız kullanıcıya "bu kayıt otomatik taşınamadı" demek için vardır.

---

## 7. Eski sürüm ve rollback uyumluluğu

- `user_version` 1 → 2. Eski sürüm `SchemaTooNewError` ile açılmayı reddeder ve
  mevcut açıklayıcı ekranı gösterir. **Bilinçli:** eski sürümün yeni
  veritabanını bayat JSON'la birlikte yorumlaması kusuru geri getirirdi.
- Gerçekten eski sürüme dönülecekse yol, göçün aldığı otomatik güvenlik
  yedeğidir.
- **Göç, JSON'dan satır taşımadan önce otomatik güvenlik yedeği alır** —
  restore'un yaptığının aynısı, aynı `create_backup` yoluyla. Geri dönüşün tek
  garantisi budur. Anahtar yoksa yedek alınamaz; o durumda göç çalışmaz ve
  JSON'a dokunulmaz.

---

## 8. Eski JSON'un emekliye ayrılması

JSON **yalnız** şunların tamamı doğrulandıktan sonra emekliye ayrılır:

1. Taşınabilir her kayıt SQL'de mevcut (UID ile sayım eşleşiyor).
2. `goal_name`, `target_amount`, `current_amount` kuruş hassasiyetinde eşit
   (`fiat()` ile karşılaştırma).
3. Göç öncesi/sonrası **hesap bakiyeleri toplamı değişmedi**.
4. `balance_events` satır sayısı değişmedi (göç defter yazmaz).
5. Göç ikinci kez çalıştırıldığında hiçbir satır eklemiyor/güncellemiyor.
6. Karantina kayıtları kullanıcıya gösterilmek üzere kaydedildi.

### Silme değil, taşıma

Dosya `savings_goals.json.migrated-<ISO>` olarak **korunur**.

- **Hassas veri:** hedef adı ve tutarlar kişisel finans verisidir. Dosya
  kullanıcı veri dizininde (`data_dir()`) kalır; kurulum dizinine ya da yeni
  bir konuma KOPYALANMAZ.
- **Bir daha okunmaz:** normal çalışma sırasında hiçbir kod yolu `.migrated`,
  `.stale` ya da `.unreadable` uzantılı dosyaları açmaz.
- **Yedek kapsamı:** bu dosyalar yedek paketine GİRMEZ; içerikleri zaten
  SQL'e taşınmış ya da karantina tablosunda kayıtlıdır. Yedeğin kapsamı
  `finance.db` + anahtar + config olarak kalır ve hedeflerin tamamı ilk
  üyenin içindedir.
- **Yaşam süresi:** otomatik silme YOK.

---

## 9. Değişecek dosyalar ve sorumlulukları

| Dosya | Sorumluluk |
|---|---|
| `database/init_db.py` | Yeni sütunlar, `UNIQUE` index, UID backfill, `NOT NULL` uygulaması, karantina + işaret tabloları, `SCHEMA_VERSION` 2 |
| `services/savings_migration.py` **(yeni)** | Göç durum makinesi, sınıflandırma, karantina, doğrulama, emeklilik. UI'dan bağımsız → doğrudan test edilebilir |
| `services/savings_service.py` | `create_goal` UID üretir; `get_goals` yeni alanları döndürür; `deposit`/`withdraw`/`delete` opsiyonel `goal_uid` ile fail-closed |
| `services/backup_service.py` | Rollback kapsamına `old-savings_goals.json`, karantina tablosu `ENCRYPTED_FIELDS`'e |
| `main.py` | JSON okuma kaldırılır; `self.savings_goals` SQL'den yüklenir; göç açılışta çağrılır; karantina bildirimi |
| `mixins/savings_mixin.py` | `self.store.put(...)` çağrıları ve `_ensure_goal_db_id` kaldırılır; render ve tüm işlemler servisten |

---

## 10. Test matrisi

| # | Test | Kapsanan |
|---|---|---|
| 1 | Temiz yeni profil | Göç no-op |
| 2 | Yalnız eski JSON profil | Tam göç |
| 3 | Yalnız SQL profil | Göç no-op |
| 4 | JSON ve SQL tam eşleşiyor | Alan tamamlama, tutar korunur |
| 5 | Kısmi ayrışma | Karma karar |
| 6 | Aynı id farklı hedef | **Karantina** |
| 7 | Aynı mantıksal hedef farklı id'lerde | **Karantina** |
| 8 | Aynı ad ve tutarda iki meşru hedef | Birleştirme YOK |
| 9 | SQL'de olmayan JSON hedefi / JSON'da olmayan SQL hedefi | INSERT / dokunma |
| 10 | Bozuk-kısmi JSON, kullanılamayan anahtar | Durdur + karantina; kısmi göç yok |
| 11 | Göç iki ve daha fazla kez | İdempotenlik |
| 12 | Her yazma/commit/rename/journal aşamasında failure injection | Mevcut `_failure_hook` deseni |
| 13 | Göç sırasında finansal toplamlar + `balance_events` replay | Değişmezlik |
| 14 | Backup → boş profil → restore | uid, ad, hedef tutarı, biriken tutar, hedef tarihi, durum, `created_at`, `color`, `auto_deposit`, bağlı hesap bakiyesi, defter değişmezleri |
| 15 | **Kimlik yeniden kullanım regresyonu** | §1(b)'nin 7 adımı; para yanlış hedefe GİTMEMELİ |
| 16 | Başka profile ait yedek restore | UID çakışması yok |
| 17 | Restore sonrası aynı süreçte UI state yenileme | Yeniden başlatma gerekmez |
| 18 | Gerçek Kivy ekranı: hedef görüntüleme, yatırma, silme | UI SQL'den besleniyor |
| 19 | Windows dosya kilidi / atomik replace | `os.replace` davranışı |
| 20 | Yeni şemayı eski sürümle açma | `SchemaTooNewError` |

Test 15 **bilinen-bozuk duruma karşı** doğrulandı: dilim 0'da bugünkü koda
karşı yazıldı ve KIRMIZI verdiği ölçüldü.

---

## 11. Uygulama dilimleri

| # | Dilim | İçerik | Risk |
|---|---|---|---|
| 0 | **Regresyon testi önce** | Test 15'i BUGÜNKÜ koda karşı yaz; kırmızı olmalı | Yok |
| 1 | Şema | Sütunlar, index, backfill, `user_version` 2, karantina + işaret tabloları | Düşük |
| 2 | Göç motoru | `savings_migration.py` + testler 1-13. UI'ya bağlanmaz | Düşük |
| 3 | Bağlama | Açılışta göç; `main.py` JSON okumayı bırakır; mixin servise geçer. Testler 15, 18 | **Yüksek** |
| 4 | Restore entegrasyonu | Rollback kapsamı, journal durumu, testler 14, 16, 17, 19 | Orta |
| 5 | Emeklilik | `.migrated` taşıma, §8 doğrulamaları, `NOT NULL`, test 20 | Düşük |

Dilim 0 kasıtlı: kusuru teste bağlamadan düzeltmeye başlamak, düzeltmenin işe
yaradığını kanıtlayamamak demektir.

---

## 12. Riskler, durma koşulları, geri alma

### Riskler

| Risk | Azaltma |
|---|---|
| Yanlış eşleştirme, hedef birleşmesi | Ad+tutar sezgisi yok; belirsizlik karantinaya |
| Göç yarıda kalır, DB tutarsız | Tek transaction; commit yoksa değişiklik yok |
| Kullanıcı hedeflerini kaybeder | Göç öncesi otomatik yedek; JSON silinmez, taşınır |
| Restore hâlâ ayrışma üretir | Dilim 4 + testler 14-17 |
| Bayat JSON tekrar etkin kaynak olur | §2.6 işareti + restore karantinası |
| `user_version` eski sürümü kilitler | Bilinçli; §7'de belgelendi |

### Durma koşulları

- Test 15 düzeltmeden sonra hâlâ parayı yanlış hedefe gönderiyorsa.
- Göç `balance_events` satır sayısını veya hesap bakiyeleri toplamını
  değiştiriyorsa.
- İdempotenlik testi ikinci koşumda fark üretiyorsa.
- Karantina kayıtları kullanıcıya ulaşmıyorsa.
- Gerçek uygulamada birikim ekranı boş açılıyorsa.

### Geri alma

Her dilim ayrı commit. Dilim 1-2 saf eklemeli ve geri alınabilir. Dilim 3'ten
sonra geri dönüş göçün aldığı güvenlik yedeğinden restore ile yapılır — bu
yüzden o yedek **dilim 3'ün ön şartıdır**, dilim 5'in değil.

---

## 13. Kapanan açık kararlar

Taslaktaki beş açık soru §0'da kapatıldı. Özet gerekçeler:

1. **`user_version` bump'ı eski sürümü kilitliyor** → bump edildi. Bump
   etmemek, eski sürümün yeni DB'yi bayat JSON'la birlikte yorumlamasına ve
   kusurun geri gelmesine izin verirdi.
2. **Karantina bildirimi** → açılışta tek seferlik diyalog; sessiz log değil.
3. **`.migrated` dosyası ömrü** → süresiz, otomatik silme yok.
4. **`auto_deposit` kullanılıyor mu** → bugün davranışa bağlı değil, ama
   kullanıcının oluşturduğu bir tercih. Taşındı, varsayılanı `false`.
   Kaldırılması ayrı bir ürün kararıdır ve bu planın kapsamında değildir.
5. **Dilim 3 en riskli adım** → gerçek Kivy ekranı üzerinde doğrulanır
   (test 18) ve dilim 3 öncesi güvenlik yedeği şarttır.
