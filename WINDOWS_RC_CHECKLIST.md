# Windows donanım doğrulama — kontrol listesi (RC-6 adayı)

> **TAMAMLANMIŞ TUR — TARİHSEL KAYIT.** Bu belge canlı bir yapılacaklar listesi
> DEĞİL. Anlattığı tur kapandı: #95 ve #97 `main`'e merge edildi, aday dal
> (`fix/dashboard-scroll-and-empty-cards`) silindi ve o iş v0.0.10'dan itibaren
> yayınlandı. Aşağıdaki `[ ]` kutuları o turdaki ölçümlerin durumunu gösterir;
> bugün yapılacak iş listesi olarak okunmamalıdır.
>
> Hâlâ geçerli olan iki kısıt (ikinci Windows hesabı ve çoklu monitör) canlı
> kayıtlarını CHANGELOG'un "Known limitations" bölümünde sürdürüyor — orası
> güncel kaynaktır.

Kaynak: `HANDOFF_RC_WINDOWS.md` §2 + PR #97 ile gelen arayüz değişiklikleri.
Amaç, "Windows integration verified" cümlesini kurabilmek için gereken
ölçümleri tek yerde toplamak.

---

## 0. Hangi yapı test edilecek

Doğrulanacak aday, #95 + #97'nin birleşimi — yani
`fix/dashboard-scroll-and-empty-cards` dalının ucu (`382f374`). Aday derleme, o
dalda elle tetiklenen `workflow_dispatch` koşusudur — `31763276265`
(Build Windows EXE), **yeşil** (Tests ve Build Linux da aynı commit'te yeşil).
Artifact indirilip ölçüldü:

```
Source commit : 382f374ae95be6d1c794805abc485397ba1aeeb7   (RC-6)
Workflow run  : 31763276265  (Build Windows EXE, head_sha eşleşiyor)
Artifact      : Archlence-Setup -> ArchlenceSetup.exe
Boyut         : 55.175.521 bayt
SHA-256       : 92016d16e279c39fbbd1429e6a77781ac690ed503f758a37276b72571f632a0f
```

```bash
gh run download 31763276265 --repo superuser-d0/archlence \
  --name Archlence-Setup --dir rc6
certutil -hashfile rc6\ArchlenceSetup.exe SHA256
```

**RC-6'da RC-5'ten farklı olarak ne var:** tek örnek kilidi artık Kivy
import'larından önce kontrol ediliyor — ikinci örnek başlatıldığında boş siyah
pencere açılmıyor (§2.4).

- [x] **Doğrulandı — 2026-08-14.** Artifact indirildi ve diskteki dosyanın
      SHA-256'sı yukarıdaki değerle birebir eşleşti. Dosya:
      `C:\Users\ckrgz\Downloads\ArchlenceSetup-RC6.exe`
      (farklı bir hash görürseniz yapı ölçtüğünüz kod değildir — durun)

- [x] **Eski RC temizliği — 2026-08-14.** `Downloads` altında kalan iki
      eski aday hash'iyle tanımlandı ve silindi: `ArchlenceSetup.exe`
      (`02b334b3…`, RC-4) ve `ArchlenceSetup-RC5.exe` (`1c976b33…`, RC-5).
      Diğer eski hash'lerle eşleşen bir Archlence installer bulunmadı;
      `ArchlenceSetup-RC6.exe` yerinde bırakıldı.

> **Neden her tur yeni yapı:** `31675937556`/`d5c9b04` içinde "Kartlarım"
> şeridinin sabit yüksekliğe döndürüldüğü düzeltme yok; `31677899610`/`0888ccb`
> (RC-4) içinde "Algoritmik Öngörü" ikon düzeltmesi yok; `31679532152`/`5671859`
> (RC-5) içinde de tek örnek kilidinin siyah pencere düzeltmesi yok. Eski bir
> yapıyla §2.2, §2.4 ya da §4 ölçmek, düzeltilmiş hâli değil gerilemiş hâli
> ölçer.

---

## 1. Kurulum ve ilk açılış

**Ölçüldü — 2026-08-13, RC-4 (`0888ccb`), Windows 11 Pro 26200, temiz profil**
(önceki profil silinerek kuruldu):

- [x] **SmartScreen / Defender.** Uyarı **çıkmadı**. README'deki "SmartScreen
      may warn" ifadesi bu makinede karşılık bulmadı; imzasız paket için
      garanti değil, farklı makinede tekrar bakılmalı.
- [x] **Yönetici olmayan kullanıcı.** Yönetici istemi **çıkmadı**; kurulum
      kullanıcı başına çalışıyor.
- [x] **İlk açılış.** Uygulama açıldı.
- [x] Profil `%LOCALAPPDATA%\Archlence` altında oluştu: `finance.db`,
      `archlence_config.json`, `Logs\`, `archlence.instance.lock`.
- [x] **Anahtar korumasının kanıtı:** dizinde yalnız `encryption.key.dpapi`
      var, düz `encryption.key` **yok** — yani anahtar doğrudan DPAPI'ye
      yazıldı. §3'ün reboot testi bu sayede gerçek koşulu ölçecek.

**Bulunan hata (RC-4'te vardı, RC-5'te düzeltildi):** "Algoritmik Öngörü"
kartının robot ikonu metnin üstüne biniyordu — kart başlıklarında düzeltilen
kusurun aynısı, genişliği verilmemiş bir `MDIcon`. Düzeltme sonrası ölçüm:
ikon 44dp, metinle arasında 15dp boşluk.

- [x] **RC-5 ile fiziksel makinede doğrulandı (2026-08-13):** "Algoritmik
      Öngörü" kartında ikon metne binmiyor. Aynı kurulum RC-4'ün üzerine
      yapıldı, yani yükseltme yolu da bu turda yürüdü — verinin korunduğu
      §5'te ayrıca teyit edilmeli.

---

## 2. #95'in bildirdiği iki hata (bu turun asıl konusu)

### 2.1 Restore dosya seçicisi — uygulamayı çökertiyordu

**Ölçüldü — 2026-08-13, RC-5, boş profil.** Ayarlar → Veriler ve Gizlilik →
"Backup Geri Yükle" tıklandı; "Backup Dosyası Seç" penceresi açıldı, dizinleri
listeledi, İPTAL ile kapandı. Uygulama ayakta kaldı, `crash.log` boş (0 bayt).

- [x] Ayarlar → Geri Yükle → dosya seçici açılıyor, **uygulama kapanmıyor**.
- [x] Seçici bir klasörün içeriğini listeleyebiliyor.
- [x] **Ölçüldü — 2026-08-14, kaynaktan, izole profil.** Seçicinin açılacağı
      yol (`restore_chooser_path`) UI'nin yedek yazdığı yolla birlikte, uçtan
      uca koşturuldu: yedek yokken ev dizinine düşüyor; "Güvenli Backup" alınca
      `create_backup` `backups` dizinini kendisi oluşturuyor ve seçici artık
      **o dizinde** açılıyor, yedek de orada listeleniyor. Yani gizli
      `AppData` sorunu kapanmış durumda.
- [x] **Geri yükleme ölçüldü — aynı turda, GERÇEK profile dokunmadan.**
      1 hesap + 1 işlem yazıldı, yedek alındı, sonra ikinci bir hesap eklendi;
      `restore_backup` sonrası hesap sayısı yedek anına döndü, sonradan eklenen
      hesap gitti, hesap adı ve işlem sayısı korundu ve Türkçe karakterli
      açıklama şifre çözümünden **birebir** geri geldi.
      Kullanıcının kendi verisiyle bu adım hâlâ yapılmadı ve bilerek
      yapılmıyor — geri yükleme mevcut verinin üzerine yazar.

### 2.2 "Kartlarım" sekmesi kaydırma

Sayfa **tepedeyken** ölçün; ara konumdan ölçmek bu hatayı gizliyor (§4, ders 1).

**Ölçüldü — 2026-08-13, RC-5, boş profil (hiç kart yok).**

- [x] **Tekerlek**, şeridin üzerindeyken sayfayı indiriyor; "Hesaplarım"
      bölümüne ulaşıldı.
- [x] **Tekerlek**, şerit dışındaki alanda da aynı şekilde çalışıyor (özet
      kutucuklarının üzerinde ölçüldü, hareket miktarı aynı).
- [x] **Sürükleme**, şeridin boş alanından dikey olarak sayfayı kaydırıyor.
- [x] **Sürükleme**, şeridin kaydırma çubuğundan yatay olarak kartları
      kaydırıyor — **ölçüldü, 2026-08-14, RC-6, 6 test kartıyla.** Şerit
      taşana kadar kart eklendi (2 kart yan yana sığıyor, taşma için 6 gerekti);
      çubuk şeridin alt kenarında bulundu (y≈742) ve basılı tutup sağa
      sürüklenince şerit 1-3. kartlardan 3-5. kartlara kaydı, çubuk da ortaya
      geldi. Tek seferlik `left_click_drag` işe yaramıyor, basma → ara
      hareketler → bırakma gerekiyor (Kivy çubuğu ani sıçramayı tıklama
      sayıyor).

> Kart yokken şerit 620dp'lik boş bir alan olarak duruyor ve "Hesaplarım"a
> inmek için o alanı kaydırıp geçmek gerekiyor. Bilinen ve kabul edilen bedel:
> şeridi içeriğe göre kısaltmak sekmenin sürüklemesini öldürüyordu (bkz.
> `HANDOFF_PR97.md` §1).

> **Bilinen sınır — hata olarak raporlamayın:** doğrudan bir KARTIN üzerinden
> sürüklemek sayfayı kaydırmaz; `MDCard` dokunuşu sahipleniyor, uygulama
> genelinde geçerli çerçeve davranışı. Kartların üzerinde **tekerlek çalışır**.
>
> **ÇÖZÜLDÜ — kapının kırmızısının sebebi ölçüldü (2026-08-14).**
> `scripts/dev/verify_tab_scrolling.py` suni dokunuşu **pencerenin tam
> ortasından** başlatıyor (`x, y = Window.width / 2, Window.height / 2`).
> Demo profiliyle o nokta doğrudan bir `PremiumCreditCardWidget`'in üstüne
> düşüyor — widget yığını ölçüldü, derinlik 13'te MDCard var. `MDCard`
> dokunuşu sahiplendiği için (yukarıdaki bilinen sınır) kapı **sağlam bir
> yapıyı kırmızı gösteriyor**. Yani bu kırmızı bir ürün hatası değil, ölçüm
> noktası hatası.
>
> Önceki not "boş profille yeşil, dolu profille kırmızı" diyordu; bu
> çerçeveleme yanlıştı ve düzeltildi: kapı profil boşsa **kendi hesaplarını
> kendisi yaratıyor** (1 vadesiz + 3 kredi kartı, satır 104-112). Yani her iki
> koşumda da kartlar var; fark yalnızca hangi yerleşimde merkez noktasının bir
> kartın üstüne denk geldiği. Bu da kapıyı kırılgan yapıyor: sonuç, kart
> sayısına ve dizilime göre değişiyor.
>
> **Düzeltme denendi ve GERİ ALINDI.** Dokunuş noktasını "kartın üstünde
> olmayan bir yer" seçecek şekilde değiştirmek kapıyı dolu profilde yeşile
> döndürdü, ama `scroll_type: ["bars"]` düzeltmesi geri alındığında da yeşil
> kaldı — yani hatayı tamamen kaçırır hâle geldi (ölçüldü). Nokta hesabı iç
> içe ScrollView'ların koordinat uzayında güvenilir çalışmıyor: seçilen nokta
> şeridin dışına düşerken "içinde" raporlanıyordu. Doğrulanamayan bir kapı
> göndermemek için değişiklik geri alındı; kapı ilk hâliyle duruyor.
>
> - [x] **Kapı yeniden ele alındı ve kanıtlandı — 2026-08-16, kaynaktan,
>       GERÇEK profil (9 hesap, aynı §5 taban çizgisi).** Dokunuş noktası
>       taşınmadı — nokta taşımanın koordinat uzayında güvenilmediği yukarıda
>       zaten ölçülmüştü. Onun yerine `ui/dashboard.kv`'deki `scroll_type:
>       ["bars"]` satırı geçici olarak `["content"]`'e çevrilip
>       `scripts/dev/verify_tab_scrolling.py` A/B çalıştırıldı:
>       düzeltme YERİNDEYKEN `sürükleme=True`, düzeltme GERİ ALINDIĞINDA aynı
>       dokunuş noktasıyla `sürükleme=False` (`::error::accounts_tab taşan
>       içeriğe rağmen kaydırılamıyor`). Temiz bir dönüş — bu da dokunuşun bir
>       `MDCard` tarafından yutulmadığının, kararı gerçekten dış
>       `ScrollView`'ın `scroll_type` kuralının verdiğinin kanıtı (kart
>       yutsaydı iki koşum da `False` verirdi). Değişiklik hemen geri alındı,
>       `git diff` boş, kapı yeşile döndü. Kod tabanında kalıcı bir değişiklik
>       yok; kanıt bu turun ölçümü.
>
> **DÜZELTME — 2026-08-17.** Yukarıdaki son cümle "dolu profildeki kırmızı
> artık gerçek bir regresyon sinyali sayılabilir" diyordu; bu fazla kesindi
> ve geri çekiliyor. O A/B, o anki gerçek yoğunlukta (1.25) koşmuştu ve
> yalnızca ORADA temiz dönüş verdiği ölçülmüştü. Yoğunluk taranınca kapı
> **density 1.0'da, gerçek 9 hesaplı profille kırmızı** veriyor — ve bu
> kırmızı bir sinyal değil:
>
> | Koşum (gerçek profil, 9 hesap) | accounts_tab |
> |---|---|
> | density 1.25 (gerçek), düzeltme yerinde | ✓ sürükleme=True |
> | density 1.25 (gerçek), düzeltme geri alınmış | ✗ sürükleme=False |
> | density 1.0 (zorlanmış), düzeltme **yerinde** | ✗ sürükleme=False |
> | density 1.0 (zorlanmış), düzeltme geri alınmış | ✗ sürükleme=False |
> | density 1.5 (zorlanmış), düzeltme yerinde | ✓ sürükleme=True |
>
> 1.0'da iki koşum da kırmızı, yani kapı orada düzeltmeyi AYIRT ETMİYOR —
> §2.2'nin başında anlatılan dokunuş-noktası artefaktının ta kendisi:
> merkez nokta o yerleşimde bir `PremiumCreditCardWidget`'in üstüne düşüyor
> ve `MDCard` dokunuşu sahipleniyor.
>
> **Kapı bu yüzden hâlâ kırılgan, ama kırılganlığın şekli değişti:** daha
> önce "profil boş/dolu" sanılıyordu, ölçülen şey **yoğunluk + hesap
> yerleşimi** kombinasyonu. CI'ın 96/192 DPI matrisinde yeşil kalmasının
> sebebi de bu — CI profili boş bulup kendi 4 hesabını yaratıyor (satır
> 104-112) ve o yerleşimde merkez noktası karta denk gelmiyor.
>
> **Ürün tarafında bulgu YOK:** düzeltmenin işe yaradığı gerçek yoğunlukta
> (1.25) ve 1.5'te ayırt edici şekilde kanıtlandı. Kırılgan olan ölçüm
> aracıydı.
>
> **KAPANDI — 2026-08-17. Kapı sağlamlaştırıldı.** Dokunuş noktası artık
> hesaplanmıyor, SEÇİLİYOR: yatay şeridin sınırları içinde bir aday ızgarası
> taranıyor ve her aday için widget ağacı `collide_point` ile gerçekten
> yoklanıp kartın üstüne düşüp düşmediği soruluyor. Aday bulunamazsa ölçüm
> `ATLANDI` olarak raporlanıyor — ölçemediği bir durumu başarısızlık saymak
> bu kapının asıl kusuruydu.
>
> Sonuç, üç yoğunlukta A/B ile doğrulandı:
>
> | Yoğunluk | Düzeltme yerinde | Düzeltme geri alınmış |
> |---|---|---|
> | 1.0 | ✓ yeşil | ✗ kırmızı |
> | 1.25 | ✓ yeşil | ✗ kırmızı |
> | 1.5 | ✓ yeşil | ✗ kırmızı |
>
> Öncesinde 1.0 hiç ayırt etmiyordu (iki koşumda da kırmızı).
>
> **Yolda bir kez yanlış yapıldı ve ölçülerek yakalandı:** ilk deneme adayı
> SAYFANIN tamamında aradı ve dokunuşu şeridin dışına taşıdı. Kapı o hâlde
> 1.0 ve 1.25'te düzeltme geri alınmışken bile YEŞİL kaldı — yani hatayı
> tamamen kaçırır hâle geldi ve 1.25 gerilemiş oldu. Bu, §2.2'nin başında
> "denendi ve geri alındı" diye kayıtlı tuzağın aynısı. Aday araması şeridin
> sınırlarına hapsedilerek düzeltildi: hata şeridin İÇİNDE yaşıyor, dışarıda
> `scroll_type` zaten etkisiz.

---

### 2.3 KAPANDI — "Ayarlar ikonu tıklamayı almıyor" sanılan şey, Archlence hatası DEĞİL

İlk gözlem doğruydu (Ayarlar'ın ikon satırı dört denemede de sonuçsuz kaldı)
ama teşhis **yanlıştı** — "muhtemelen KivyMD'nin dokunma alanı kayması" diye
yazılmıştı, geri çekiliyor. Sebep koda hiç dokunmadan, ölçülerek bulundu:

Ekranı kontrol etmek için kullanılan **Claude uygulamasının kendi penceresi**
o anda gerçek masaüstünde `(989,20)-(1523,747)` dikdörtgeninde duruyordu ve
Archlence penceresinin önündeydi (z-sırasında üstte). Alt gezinme beş eşit
sütuna bölünüyor; "Ayarlar" sütunu `[1012,1175]` tamamen bu pencerenin x
aralığının içinde kalıyor, "Araçlar" sütununun da yalnız en sağ ~13px'i
kesişiyor. Dört noktalı A/B/A ölçümü kesin sonuç verdi:

| Nokta | Konum | Sonuç |
|---|---|---|
| Araçlar'ın en sağ dilimi, Claude'un altında | x=905, y=640/656 | ✗ başarısız |
| Aynı x=905, Claude penceresinin dışında | x=905, y=690 | ✓ başarılı |
| Araçlar'ın kendi güvenli bölgesi | x=860, y=640 | ✓ başarılı |
| Pencere başka bir ekran konumuna taşındığında | — | dead zone tamamen kayboldu |
| Pencere eski konumuna geri taşındığında | — | dead zone aynen geri geldi |

Yani dokunuş Archlence'a hiç ulaşmıyordu; üstteki pencere yutuyordu. `crash.log`
boş olması da bununla tutarlı — istisna yok, çünkü olay uygulamaya hiç
gelmedi. Realtek Audio Console de aynı bölgede görünür bir pencereydi ve önce
o şüphelenildi; kapatılıp aynı test tekrarlandığında dead zone **değişmedi**,
yani o suçlu değildi.

**Sonuç:** kod tarafında yapılacak bir şey yok. Bu bulgu, kullanıcının ilk kez
manuel testte rastladığı "Ayarlar açılmıyor" durumuyla aynı kalıpta olabilir —
eğer o sırada ekranda Archlence'ın üzerine binen başka bir pencere (bir sohbet/
asistan penceresi dahil) varsa. Gerçek bir kullanıcı hatası bildirirse, önce
ekranda üst üste binen başka pencere olup olmadığı sorulmalı.

---

### 2.4 Tek örnek kilidi — ölçülmesi gereken açık madde

2026-08-14 gecesi paketlenmiş uygulama açıldı, giriş yapıldı (profil dosyaları
00:07-00:08'de yazıldı), sonra süreç listesinde kalmadı. Aynı anda
`archlence.instance.lock` **başka bir süreç tarafından tutuluyordu** — makinede
VS Code'un debugpy oturumları depo `.venv`'i ile çalışıyordu. `crash.log` boş.

Bu bir hata raporu DEĞİL, ölçülmemiş bir durum: kilit tutulduğunda uygulamanın
tasarlanmış davranışı sessiz çıkış değil, Kivy'den önce yerel bir Windows uyarı
kutusu ve `SystemExit(2)`'dir (`utils/single_instance.py::notify_already_running`).
O kutunun paketlenmiş yapıda gerçekten göründüğü hiç doğrulanmadı — kod yolu
Kivy başlamadan çalıştığı için paketlemeye duyarlı.

- [x] **Ölçüldü — 2026-08-14, RC-5.** Kaynaktan çalışan bir örnek kilidi
      tutarken paketlenmiş uygulama başlatıldı: yerel uyarı kutusu **çıktı** —
      "Archlence bu kullanıcı profili için zaten çalışıyor." OK'a basınca ikinci
      örnek çıktı (süreç listesinden düştü), ilk örnek etkilenmeden ayakta
      kaldı. Yani tek-örnek koruması paketlenmiş yapıda çalışıyor.
      **Yan bulgu:** kutu görünmeden önce ekranda boş bir **siyah uygulama
      penceresi** açılıyor ve kutu kapatılana kadar duruyor. Koddaki not
      ("Kivy/SQLite başlangıcından ÖNCE") paketlenmiş yapıda tam olarak
      geçerli değil: pencere kilit kontrolünden önce oluşuyor. Kozmetik ama
      kullanıcı "açıldı sanıp" siyah pencereye bakıyor.
- [x] **DÜZELTİLDİ — siyah pencere.** Kilit kontrolü `main.py`'ın sonundaki
      `__main__` bloğundan alınıp Kivy import'larından ÖNCEye (bölüm 2.5)
      taşındı; bırakma işini `atexit` üstleniyor, böylece aradaki erken
      `SystemExit` yolları da kapsanıyor. Kaynaktan ölçüldü: ikinci örneğin
      çıktısı artık **tamamen boş** — tek satır Kivy başlangıç logu bile yok,
      yani pencere hiç açılmıyor. Öncesinde ikinci örnek tüm Kivy başlangıcını
      koşturup pencereyi açıyordu. `tests/test_single_instance_startup_order.py`
      sırayı sabitliyor ve düzeltme öncesi `main.py`'a karşı 4 testin 3'ü
      kırmızıya dönerek kapının gerçekten ölçtüğü doğrulandı.
      **Fiziksel doğrulama RC-5'te YAPILAMAZ** — düzeltme o yapıdan sonra
      geldi; RC-6 ile bakıldı, aşağıya bakın.
- [x] **RC-6 ile fiziksel makinede DOĞRULANDI — 2026-08-14.** Kurulu RC-6
      çalışırken (kilidi tutan örnek) ikinci örnek başlatıldı ve ikinci
      sürecin görünür pencereleri 200ms aralıklarla, başlatmadan çıkışa kadar
      tek bir ölçümde toplandı. **Yaşamı boyunca görülen tek pencere sınıfı
      `#32770`** (Windows diyalog kutusu) — Kivy/SDL penceresi (`SDL_app`)
      hiç oluşmadı. Kutu kapatılınca süreç çıktı, ilk örnek etkilenmedi.
      Ölçüm ekran görüntüsüyle değil pencere sınıfı numaralandırmasıyla
      yapıldı; "siyah pencere görülmedi" öznel gözlemine değil, SDL
      penceresinin hiç yaratılmadığına dayanıyor.
- [x] **Ölçüldü — 2026-08-14, kaynaktan, izole profil. Bayat kilit sorunu YOK.**
      Çalışan örnek `Stop-Process -Force` ile öldürüldü (Görev Yöneticisi ile
      aynı yol); kilit dosyası diskte kaldı ama işletim sistemi kilidi bıraktı
      (`msvcrt.locking` handle kapanınca serbest kalıyor). Hemen ardından
      başlatılan yeni örnek **tam açıldı**. Yani çökme/zorla kapatma sonrası
      uygulama kilitlenmiyor.
- [ ] Geliştirme oturumu (kaynaktan çalışan örnek) ile paketlenmiş örnek aynı
      profili paylaşıyor: bu beklenen mi, yoksa geliştirme ayrı profile mi
      yönlendirilmeli? **Karar bu RC turunun dışında ayrı bir iş olarak
      izleniyor; mevcut davranış bu turda değiştirilmedi.**

---

### 2.5 Arama çubuğu hiç bağlanmamıştı — kullanıcı bulgusu

**Bildirim (2026-08-17):** "üstteki arama butonu hiçbir şekilde çalışmıyor."
Rapor doğru çıktı ve sebebi beklenenlerin hiçbiri değildi — regresyon değil,
DPI ile ilgisi yok, §2.3'teki pencere örtüşmesi artefaktı da değil.

**Ölçüldü, kaynaktan:**

| Kontrol | Sonuç |
|---|---|
| Büyüteç ikonunun tipi | `MDIcon` — `MDIconButton` DEĞİL |
| `MDIcon` → `ButtonBehavior` mirası | **False** (yani hiç buton değil, tıklama olayı almıyor) |
| `home_search_input.on_text_validate` bağlayıcı sayısı | **0** (Enter de bir şey yapmıyor) |
| `services/` altında arama servisi | Yok |
| `home_search_input` kodda kaç yerde geçiyor | 2: kendi tanımı + yalnızca GÖRSEL kapı |

Git geçmişi: alan `0a905a1`'de eklendi ve o commit'in konusu
**"fix: remove search and header render seams"** — yani işi görsel bir dikiş
kusurunu düzeltmekti, işlevsellik eklemek değil. Tüm geçmişte hiçbir zaman
bir işleyiciye bağlanmadı; v0.0.9'da da aynıydı. ROADMAP, README ve
CHANGELOG'da arama özelliğinden hiç söz edilmiyordu — "yakında" olarak bile
kayıtlı değildi.

**Neden hiçbir kapı yakalamadı:** tek kapısı `verify_search_bar_visual.py`
ve adı üstünde, yalnızca çubuğun nasıl GÖRÜNDÜĞÜNÜ ölçüyor. Bu ders bu turun
en genellenebilir bulgusu: **bir kontrolün doğru çizildiğini ölçmek, bir şey
yaptığını ölçmez.**

**İlk yapılan (0.0.10):** çubuk ana ekrandan kaldırıldı, görsel kapının CI
adımı yoruma alındı, bileşen ve dikiş düzeltmesi korundu.

**Sonra UYGULANDI — 2026-08-17.** Kapsam kullanıcı tarafından belirlendi:
hesap ve kategori adları. `services/search_service.py` (saf eşleştirme +
SQL okuma) ve `mixins/search_mixin.py` (300 ms debounce, satır içi sonuç
paneli). Büyüteç artık `MDIconButton` ve alanı odaklıyor. Görsel kapı
parktan çıkarıldı; beş senaryonun beşi de yeşil.

Canlı uygulamada ölçüldü: `"kart"` → 5 hesap satırı, `"nakit"` → 2 satır,
`"zzzzz"` → "Sonuç bulunamadı", temizlik sonrası panel 0 satır / 0 yükseklik.

**Bu turun asıl teknik bulgusu Türkçe katlama.** Depodaki iki eski arama
kutusu düz `.casefold()` kullanıyor ve bu Türkçe'de YANLIŞ:
`"I".casefold()` → `"i"` ama `"ı".casefold()` → `"ı"`, yani "ISI" yazan
kullanıcı "ısı" kaydını bulamaz; `"İ".casefold()` ise `"i"` + U+0307
üretiyor — görsel olarak "i" ama eşit değil. `normalize()` üçünü de aynı
yere indiriyor, aksanları da katlıyor ("sirket" → "Şirket").
21 birim testi bunu sabitliyor ve kapı bilinen-bozuk duruma karşı
doğrulandı: `ı→i` katlaması kaldırılınca 5 test kırmızıya döndü.

**Kalan iki iş `docs/ROADMAP.md` Phase 2'de:** şifreli işlem açıklamalarında
arama (SQL'e itilemez, 50K işlemde tam çözüm 1,1 sn) ve eski iki arama
kutusunun aynı `normalize()`'a geçirilmesi.

## 3. DPAPI — veri kaybı riski en yüksek madde

Ana Windows kullanıcısındaki reboot yolu RC-6 ile ölçüldü. Farklı bir
Windows kullanıcısıyla kullanıcılar arası yalıtım kontrolü açık kaldı.

- [x] **RC-6, 2026-08-14:** Reboot öncesi 3 test hesabı ve 1 test işlemi
      kaydedildi; uygulama normal kapatıldı.
- [x] `%LOCALAPPDATA%\Archlence` altında `encryption.key.dpapi` mevcut
      (288 bayt); düz `encryption.key` **yok**. `crash.log` 0 bayttı.
- [x] **Makine yeniden başlatıldı — 2026-08-14.**
- [x] Reboot sonrası RC-6 açıldı; kullanıcı hesap adlarının,
      tutarların ve işlem açıklamasının olduğu gibi durduğunu
      doğruladı. Salt-okunur DB sayımı da 3 hesap / 1 işlem verdi;
      `encryption.key.dpapi` yerinde, düz anahtar yok ve `crash.log` boş.
      "Kayıtlar okunamadı" uyarısı çıkarsa anahtar kaybedilmiş demektir — bu
      bir bloklayıcıdır.
- [x] Ayarlar → “Şifreleme Anahtarı” satırı reboot öncesinde
      **Windows DPAPI** gösterdi.
- [ ] Aynı kontrolü **ikinci bir Windows kullanıcı hesabıyla** tekrarlayın —
      DPAPI kullanıcı başına; başka kullanıcı sizin verinizi açamamalı.
      **Fiziksel koşum YAPILAMAZ — 2026-08-17 teyit edildi:** makinede ikinci
      bir Windows hesabı yok ve oluşturulmayacak. Bu madde bu makinede
      uçtan uca kapanamaz; aşağıdaki ölçüm onun YERİNE GEÇMEZ, kapsamı
      daraltır.

      **MEKANİZMA ÖLÇÜLDÜ ve kapıya bağlandı — 2026-08-17.** İzolasyon
      iddiası tek bir şeye dayanıyor: `CryptProtectData`'ya
      `CRYPTPROTECT_LOCAL_MACHINE` (0x4) verilip verilmediği. Verilirse blob
      MAKİNEYE bağlanır ve o makinedeki her Windows kullanıcısı çözer;
      verilmezse çağıran KULLANICIYA bağlanır. Kod `dwFlags=0` geçiyor.

      Bu, kaynak metni aranarak değil **davranışsal olarak** ölçüldü: gerçek
      `CryptProtectData` çağrısının arasına girilip `dwFlags` yakalandı
      (`tests/test_windows_platform_contracts.py::RealWindowsDpapi`,
      koruma ve çözme tarafı ayrı ayrı). Kapı bilinen-bozuk duruma karşı
      doğrulandı: bayrak `0x4` yapılınca test kırmızıya döndü
      ("anahtar MAKİNE kapsamıyla korunuyor"), geri alınca yeşile.

      | | |
      |---|---|
      | **Kanıtlar** | Windows kendi sözleşmesi gereği blob'u çağıran kullanıcıya bağlar; başka kullanıcı çözemez. Ve biri ileride bu bayrağı eklerse sessizce değil, kırmızı kapıyla olur. |
      | **Kanıtlamaz** | Windows'un kendi sözleşmesine uyduğunu (işletim sistemine güveniyoruz) ve gerçek bir ikinci hesapla koşulduğunu. |

      **Kalan risk kabul ediliyor** ve CHANGELOG'un Known limitations
      bölümünde bu şekilde yazılı — "doğrulandı" olarak DEĞİL.

---

## 4. PR #97'nin getirdiği arayüz değişiklikleri

Hepsi Linux/geliştirme makinesinde ölçüldü; burada yalnız gerçek makinede
doğrulanıyor.

**Ölçüm turu — 2026-08-14, RC-6, gerçek profil + test verisi** (6 kredi kartı,
2 borç, 11 varlık kaydı script ile eklendi; varlıklardan bazıları iki ekleme
turu yüzünden yinelenmiş durumda — test verisi, uygulama hatası değil).

- [x] **Tekerlek, kart içi listelerin üzerinde sayfayı kaydırıyor.** Ana
      sayfada Aktif Abonelikler / Aktif Gelirler / Olağandışı Harcamalar /
      Aktif Borçlar / Yaklaşan Ödemeler kartlarının üzerinden ve Varlıklarım
      sekmesinde "Aktif Varlıklarım" listesinin ÜZERİNDEN tekerlekle sayfa
      kaydırıldı; Kartlarım'da doğrudan bir kredi kartı widget'ının üzerinden
      de çalıştı. Eski ölü bölge yok.
- [x] **Liste kendi içinde kaydırılabiliyor — ölçüldü, 2026-08-14, kaynaktan,
      izole profil.** Ekran gerektirmeyen bir yolla: sentetik tekerlek
      olayını olay döngüsünden göndermek bu harness'ta asılı kaldığı için
      (ölçüldü), kararın alındığı tek yer doğrudan sınandı —
      `_WheelPassthroughMixin._wheel_can_scroll`, gerçek widget ve gerçek
      geometri üzerinde (4 borç satırı, kart 290dp'de sınırlı, içerik
      590dp — taşıyor). Liste ortadayken tekerleği kendinde tutuyor (her iki
      yön), dibindeyken aşağı yönü, tepesindeyken yukarı yönü sayfaya
      bırakıyor. **Kapı bilinen-bozuk duruma karşı doğrulandı:** sınır
      kontrolü kaldırılınca (`return True` ile değiştirildi) test kırmızıya
      döndü, geri alınca yeşile döndü.
      Yan not: bu ölçümün ilk hâli kendi ölçüm aracımın hatasıyla yanlış
      kırmızı veriyordu — `collide_point`'e pencere koordinatı yerine widget'in
      ebeveynine göre yerel koordinat vermek gerekiyormuş; düzeltilip
      doğrulandı.
- [x] **Boş kartlar mesajları kadar yer kaplıyor.** Ana sayfada Aktif
      Aboneliklerim / Aktif Gelirlerim / Olağandışı Harcamalar ve Varlıklarım
      sekmesinde Varlık Geçmişi kartları, tek satırlık mesajlarıyla derli
      toplu duruyor; eski ekran dolusu boşluk yok.
- [x] **Boş dönem — ölçüldü, 2026-08-14, kaynaktan, izole profil.** Sıfır
      işlemli bir profilde: liste alanı tamamen kapandı (0dp), boş durum
      etiketi görünür (opaklık 1, yükseklik 40dp) ve metin birebir
      "Bu dönemde işlem bulunmuyor." — beş kontrolün beşi de geçti.
- [x] **Dolu profil, borç kartı iki satır — ölçüldü, 2026-08-14, kaynaktan,
      izole profil.** İki borç eklenip `load_active_debts()` ile açıkça
      tazelenerek: kart 362dp, görünür alan 290dp, içerik 290dp, iki satır da
      çizildi ve ikisi de görünür alanın sınırları içinde (kırpılma yok).
      İçerik görünür alana tam sığıyor, iç kaydırma gerekmiyor.
      Not: ana sayfanın borç listesinin yalnız uygulama açılışında
      yüklenmesi (sekme değişince tazelenmemesi) ayrı bir gözlem — bu
      yüzden RC-6 üzerinde ekrandan gösterilemedi, bilinen bir uygulama
      davranışı, kod hatası olarak işaretlenmedi.
- [x] **Varlık sekmesi**: "Aktif Varlıklarım" ve "Varlık Geçmişi" kartları
      **birbirinin üstüne binmiyor** — 11 varlık kaydıyla, kartın alt sınırı
      ile "Varlık Geçmişi" başlığı arasındaki sınır yakınlaştırılarak
      doğrulandı. Bu turun düzeltilen asıl hatasıydı (satırlar alttaki kartın
      üstüne taşıyordu).
- [x] **Başlık ikonları yazıya binmiyor.** Fiziksel olarak görülenler:
      Algoritmik Öngörü (robot), Finansal Sağlık Skoru, Aktif Aboneliklerim,
      Aktif Gelirlerim, Olağandışı Harcamalar, Aktif Borçlarım, Yaklaşan
      Ödemeler, Aktif Varlıklarım, Varlık Geçmişi. "Bekleyen İşlemler" kartı
      bu profilde görünmüyor (bekleyen işlem yok), ölçülemedi.

---

## 5. Yükseltme ve kaldırma

- [x] **RC-5 → RC-6 yükseltme — 2026-08-14, fiziksel Windows kurulumu.**
      RC-5 sessiz kuruldu; profil 9 hesap / 1 işlem / 2 aktif borç / 11
      aktif varlıkla yerinde kaldı ve işlemin iki şifreli alanı DPAPI ile
      çözüldü. RC-6 bunun üzerine kuruldu (`exit 0`); satır sayıları,
      DB hash'i (`39f22647…`) ve DPAPI anahtar hash'i (`913adc03…`)
      değişmedi, şifreli işlem yeniden çözüldü.
- [x] **Kaldırma — aynı tur.** Resmî `unins000.exe` `exit 0` verdi;
      `%LOCALAPPDATA%\Programs\Archlence` ve `Archlence.exe` kalktı.
      `%LOCALAPPDATA%\Archlence`, `finance.db` ve `encryption.key.dpapi`
      yerinde kaldı.
- [x] **Yeniden kurma — aynı tur.** Hash'i doğrulanmış RC-6 yeniden
      kuruldu (`exit 0`), program dosyası geri geldi. Profil yine 9/1/2/11
      satır verdi; DB ve anahtar hash'leri taban çizgisiyle aynı kaldı ve
      eski şifreli işlem alanları (`2.0`, `Aidat`) başarıyla çözüldü.
      Paketlenmiş `Archlence.exe` yeniden başlatıldı; ana pencere
      “Archlence” başlığıyla canlı kaldı ve `crash.log` 0 bayttı.

---

## 6. Ortam matrisi

- [x] Türkçe klavye: tutar alanlarına `1.234,56` yazımı, ı/İ/ğ/ş içeren
      açıklamalar kaydedilip geri okunuyor.
      **Kısmen kapatıldı (2026-08-14, kaynaktan):** yazımın uygulama
      tarafındaki yolu zaten birim testlerinde kapsanıyor —
      `tests/test_formatters.py` Kivy'nin gerçek `insert_text` sırasını taklit
      eden bir alanla tuş tuş yazıyor (`type_at`) ve bir zamanlar sayıyı
      bozan imleç hatasını da pinliyor (`1234567` -> `1.235.674`). 47 test
      yeşil. Türkçe karakterli açıklamanın şifreleme + DB + yedek/geri yükleme
      turundan **birebir** geçtiği de ayrıca ölçüldü (§2.1 zincir testi).
      **Geriye kalan yalnızca fiziksel klavye düzeni:** Türkçe Q düzeninde
      basılan tuşların doğru karakterleri üretmesi işletim sistemi tarafıdır
      ve elle denenmelidir. **Ortam envanteri — 2026-08-14:** etkin giriş
      yöntemleri arasında Türkçe Q (`0000041F`) var; ancak otomatik tuş
      gönderimi fiziksel klavyeyi ölçmeyeceği için madde işaretlenmedi.

      **KAPANDI — 2026-08-17, kullanıcı fiziksel klavyeyle denedi, sorun
      bildirilmedi.** Geriye kalan tek parça buydu ve yalnızca insan
      deneyebilirdi; otomatik tuş gönderimi işletim sisteminin düzen
      katmanını atlar. Kullanıcının aynı oturumda bildirdiği tek kusur
      klavyeyle ilgili değildi (arama çubuğu — bkz. §2.5).
- [x] %125 ve %150 DPI: metin kırpılmıyor, ikon/başlık hizaları bozulmuyor
      (bu turda düzeltilen kusur tam olarak buydu).
      **Kısmen kapatıldı (2026-08-14, kaynaktan, `KIVY_METRICS_DENSITY` ile
      simüle edilerek).** `scripts/dev/verify_icon_label_layout.py` beş
      sekmenin tamamını 1.0/1.25/1.5 yoğunluklarında taradı: 22 ikon+etiket
      çifti, 131 etiket, üçünde de sıfır çakışma/kırpılma. Kapı bilinen-bozuk
      duruma karşı doğrulandı (genişliksiz bırakılan ikon kırmızı veriyor) ve
      artık CI'ın visual-regression matrisine bağlı — her PR'da otomatik koşar.
      **Geriye kalan yalnızca gerçek Windows ölçek değişimi:** `KIVY_METRICS_DENSITY`
      uygulamanın kendi ölçeğini taklit ediyor; işletim sisteminin %125/%150
      ayarının pencere yöneticisi/DPI-farkındalık katmanında yarattığı
      farklar (bulanıklaşma, yanlış izleyici seçimi, pencere yeniden boyutlanma
      olayları) simüle edilemez, gerçek makinede denenmeli.
      **Ortam envanteri — 2026-08-14:** Win32 `GetDpiForSystem` 96 DPI / %100
      verdi. %125 ve %150, oturumun gerçek Windows ölçeği değiştirilmeden
      doğrulanmış sayılmadı.

      **%125 KAPANDI — 2026-08-17, gerçek Windows ölçeği, kaynaktan.**
      Kullanıcı ekran ölçeğini %125'e aldı ve ölçüm simülasyonsuz yapıldı:

      | Ölçüm | Değer |
      |---|---|
      | `GetDpiForSystem` / `GetDpiForMonitor` | 120 → %125 |
      | Ekran (fiziksel) | 1920×1200 |
      | Pencere farkındalığı (`GetWindowDpiAwarenessContext`) | `PER_MONITOR_AWARE` |
      | `GetDpiForWindow` | 120 |
      | Kivy `Metrics.density` / `dp(100)` / `sp(16)` | 1.25 / 125 / 20 |
      | `verify_icon_label_layout.py` (override YOK) | 38 çift, 0 çakışma |
      | `verify_tab_scrolling.py` (override YOK) | 3/3 sekme kaydırılabilir |

      **Öngörülen bulanıklaşma GERÇEKLEŞMEDİ ve sebebi ölçüldü.** Kodda,
      `.spec`'te ve `.iss`'te hiçbir DPI farkındalığı beyanı YOK (arandı,
      bulunamadı) — ama SDL2 bunu runtime'da kendisi yapıyor, pencere
      per-monitor aware doğuyor. Yani Windows bitmap ölçekleme yapmıyor,
      uygulama 120 DPI'da natif çiziyor. Bu farkındalık uygulamanın kendi
      kararı DEĞİL, bağımlılığın davranışı; SDL2 sürümü değişirse yeniden
      ölçülmeli.

      **Simülasyonun geçerliliği kanıtlandı:** gerçek yoğunluk tam olarak
      1.25 çıktı ve `KIVY_METRICS_DENSITY=1.0/1.5` ile zorlanan koşumlar
      içerik yüksekliğini tam orantılı değiştirdi (1188 → 1485 → 1782,
      yani ×1.25 ve ×1.5). Yani önceki simüle ölçümler bu makinede geçerli.

      **%150 de KAPANDI — 2026-08-17, aynı yöntem, aynı oturum.**
      Ölçek %150'ye alındı ve ölçüm yine simülasyonsuz yapıldı:

      | Ölçüm | Değer |
      |---|---|
      | `GetDpiForSystem` / `GetDpiForMonitor` | 144 → %150 |
      | Pencere farkındalığı | `PER_MONITOR_AWARE` |
      | `GetDpiForWindow` | 144 |
      | Kivy `Metrics.density` / `dp(100)` / `sp(16)` | 1.5 / 150 / 24 |
      | Pencere istemci alanı | 1200×900 (px) |
      | `verify_icon_label_layout.py` (override YOK) | 38 çift, 0 çakışma, `1dp = 1.50px` |
      | `verify_tab_scrolling.py` (override YOK) | 3/3 sekme kaydırılabilir |

      Not: ilk `sp()` ölçümü ekrana `-24.0` gibi düştü ve gerçek bir kusur
      sanıldı; dikkatli tekrar ölçümde tüm `sp` değerleri doğru ve pozitif
      çıktı (8→12, 12→18, 14→21, 16→24, 20→30, 24→36) ve elle hesapla
      (`16 × density × fontscale`) birebir uyuştu. Kusur yok, okuma hatasıydı.

      **Bu maddenin tamamı kapandı** — %125 ve %150, ikisi de gerçek
      işletim sistemi ölçeğinde ölçüldü.
- [ ] Çoklu monitör: pencere ikinci ekrana taşındığında ölçek bozulmuyor.
      **Ölçülemedi — 2026-08-14:** doğrulama makinesinde ikinci monitör
      bulunmuyor; WinForms ekran sayımı yalnız `DISPLAY1` verdi
      (1536×960, birincil). Bu bir başarısızlık değil; donanım eksikliği
      nedeniyle madde açık bırakıldı.

---

## 7. Bir şey kırılırsa

- Log: `%LOCALAPPDATA%\Archlence\log\crash.log`
- Kaydedin: hangi yapı (SHA-256), hangi adım, tam hata metni, ekran görüntüsü,
  Windows sürümü ve DPI ayarı.
- Çökme varsa uygulamayı yeniden açmadan ÖNCE `crash.log`'u kopyalayın.

---

## 8. Sonuç

**Üçü de yapıldı — 2026-08-17.** Kutular kapatıldı, çünkü işaretsiz bırakmak
tamamlanmış işi bekleyen iş gibi gösteriyordu.

- [x] §2 ve §3 → #95 draft'tan çıkarıldı, `main` ile güncellendi ve 10/10 yeşil
      kontrolle merge edildi.
- [x] §4 → #97'nin hedefi `main`'e çevrildi ve merge edildi. Bu aynı zamanda
      gerçek bir CI kör noktasını kapattı: PR'ın tabanı `main` olmadığı için
      workflow'lar hiç tetiklenmiyordu ve koşumlar elle yapılıyordu.
- [x] Kalan bulgular CHANGELOG'un "Known limitations" bölümüne yazıldı; canlı
      kayıt orada tutuluyor, bu belgede değil.
