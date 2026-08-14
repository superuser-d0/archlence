# Windows donanım doğrulama — kontrol listesi (RC-6 adayı)

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

- [ ] Eski RC'ler diskten silindi — `151506a3…`, `094ead55…`, `3a64aafd…`
      (RC-3), `02b334b3…` (RC-4), `1c976b33…` (RC-5) ve `31675937556` koşusundan inen yapı

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
> - [ ] Kapı yeniden ele alınacak: dokunuş, şeridin İÇİNDE ama kartın
>       üstünde olmayan bir noktadan başlamalı ve düzeltme geri alındığında
>       kırmızıya döndüğü kanıtlanmalı. Kanıtlanamıyorsa kapı olduğu gibi
>       bırakılmalı ve dolu profildeki kırmızısı "bilinen yanlış pozitif"
>       olarak belgelenmeli.

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
      yönlendirilmeli?

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

- [ ] Önceki sürümü kurup veri girin → RC-6'ya **yükseltin** → veri duruyor mu?
- [ ] **Kaldırın** → kullanıcı verisi korunuyor mu (profil dizini silinmemeli),
      program dosyaları temizleniyor mu?
- [ ] **Yeniden kurun** → eski veri geri geliyor mu, anahtar hâlâ çözebiliyor mu?

---

## 6. Ortam matrisi

- [ ] Türkçe klavye: tutar alanlarına `1.234,56` yazımı, ı/İ/ğ/ş içeren
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
      ve elle denenmelidir.
- [ ] %125 ve %150 DPI: metin kırpılmıyor, ikon/başlık hizaları bozulmuyor
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
- [ ] Çoklu monitör: pencere ikinci ekrana taşındığında ölçek bozulmuyor.
      **Ölçülemedi — 2026-08-14:** doğrulama makinesinde ikinci monitör
      bulunmuyor. Bu bir başarısızlık değil; donanım eksikliği nedeniyle
      madde açık bırakıldı.

---

## 7. Bir şey kırılırsa

- Log: `%LOCALAPPDATA%\Archlence\log\crash.log`
- Kaydedin: hangi yapı (SHA-256), hangi adım, tam hata metni, ekran görüntüsü,
  Windows sürümü ve DPI ayarı.
- Çökme varsa uygulamayı yeniden açmadan ÖNCE `crash.log`'u kopyalayın.

---

## 8. Sonuç

- [ ] §2 ve §3 tamamen yeşil → #95 `gh pr ready 95` ile draft'tan çıkarılabilir
      (karar depo sahibinin).
- [ ] §4 yeşil → #97 hedefi `main`'e döner, CI kontrolleri orada koşar.
- [ ] Kalan bulgular `HANDOFF_RC_WINDOWS.md`'ye değil, CHANGELOG'un
      "Known limitations" bölümüne veya yeni bir issue'ya yazılır.
