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

- [ ] İndirdiğiniz dosyanın SHA-256'sı yukarıdaki değerle **birebir** aynı
      (farklıysa yapı sizin ölçtüğünüz kod değildir — durun)

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
- [ ] Kendi yedeğinize seçiciden ulaşabiliyor musunuz — `data_dir()/backups`
      altındaki dosyalar görünüyor mu? **Henüz ölçülemedi:** bu profilde hiç
      yedek yok, seçici `AppData\Local` içinde açıldı. Önce "Güvenli Backup
      Oluştur" ile bir yedek alıp tekrar bakın.
- [ ] Bir yedeği gerçekten geri yükleyin ve verinin döndüğünü doğrulayın.
      (Bilerek yapılmadı: geri yükleme mevcut verinin üzerine yazar.)

### 2.2 "Kartlarım" sekmesi kaydırma

Sayfa **tepedeyken** ölçün; ara konumdan ölçmek bu hatayı gizliyor (§4, ders 1).

**Ölçüldü — 2026-08-13, RC-5, boş profil (hiç kart yok).**

- [x] **Tekerlek**, şeridin üzerindeyken sayfayı indiriyor; "Hesaplarım"
      bölümüne ulaşıldı.
- [x] **Tekerlek**, şerit dışındaki alanda da aynı şekilde çalışıyor (özet
      kutucuklarının üzerinde ölçüldü, hareket miktarı aynı).
- [x] **Sürükleme**, şeridin boş alanından dikey olarak sayfayı kaydırıyor.
- [ ] **Sürükleme**, şeridin kaydırma çubuğundan yatay olarak kartları
      kaydırıyor — **kart olmadığı için ölçülemedi.** En az bir kart ekleyip
      tekrar bakın; kapının dolu profildeki kırmızısı da ancak o zaman
      açıklanabilir.

> Kart yokken şerit 620dp'lik boş bir alan olarak duruyor ve "Hesaplarım"a
> inmek için o alanı kaydırıp geçmek gerekiyor. Bilinen ve kabul edilen bedel:
> şeridi içeriğe göre kısaltmak sekmenin sürüklemesini öldürüyordu (bkz.
> `HANDOFF_PR97.md` §1).

> **Bilinen sınır — hata olarak raporlamayın:** doğrudan bir KARTIN üzerinden
> sürüklemek sayfayı kaydırmaz; `MDCard` dokunuşu sahipleniyor, uygulama
> genelinde geçerli çerçeve davranışı. Kartların üzerinde **tekerlek çalışır**.
>
> **Ölçüm notu:** `scripts/dev/verify_tab_scrolling.py` **boş profille** yeşil
> (sürükleme ✓, tekerlek ✓) — CI de bu profille koşuyor. **Dolu profille**
> aynı kapı `sürükleme=False` veriyor; bu, #95'in ucunda da böyle. Sebebi
> büyük olasılıkla yukarıdaki bilinen sınır: kart sayısı arttıkça sürükleme
> noktası bir kartın üzerine denk geliyor ve `MDCard` dokunuşu yutuyor.
> Fiziksel makinede **dolu bir profille** sürükleyip hangi durumda olduğunuzu
> ölçün: elle çalışıyorsa kapı yanlış noktadan ölçüyor demektir ve
> düzeltilmelidir (§4'teki kural: kapı bilinen-bozuk yapıya karşı kırmızıya
> dönmeli). Elle de çalışmıyorsa bu, kartların üzerinden sürüklemenin gerçek
> sınırı olarak kayda geçmeli.

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
      geldi; RC-6 ile tekrar bakılmalı.
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

İki turdur devrediyor, hâlâ ölçülmedi. Şifreli veriye erişimi kaybettirebilecek
tek senaryo bu.

- [ ] Birkaç işlem/hesap girin, uygulamayı kapatın.
- [ ] `%LOCALAPPDATA%\Archlence` altında anahtarın nerede olduğunu not edin:
      `encryption.key` dosyası var mı, `encryption.key.dpapi` var mı?
- [ ] **Makineyi yeniden başlatın.**
- [ ] Uygulamayı açın: tutarlar, açıklamalar, hesap adları **doğru geliyor mu**?
      "Kayıtlar okunamadı" uyarısı çıkarsa anahtar kaybedilmiş demektir — bu
      bir bloklayıcıdır.
- [ ] Ayarlar → anahtarın hangi mekanizmayla korunduğunu gösteren metin ne
      diyor (DPAPI mi, izinli dosya mı)?
- [ ] Aynı kontrolü **ikinci bir Windows kullanıcı hesabıyla** tekrarlayın —
      DPAPI kullanıcı başına; başka kullanıcı sizin verinizi açamamalı.

---

## 4. PR #97'nin getirdiği arayüz değişiklikleri

Hepsi Linux/geliştirme makinesinde ölçüldü; burada yalnız gerçek makinede
doğrulanıyor.

- [ ] **Tekerlek, kart içi listelerin üzerinde sayfayı kaydırıyor.** Test
      noktaları: Varlık Geçmişi listesi (başlığın hemen altı — eski ölü bölge),
      Aktif Abonelikler, Aktif Gelirler, Aktif Borçlar, Yaklaşan Ödemeler,
      Son İşlemler, Aktif Varlıklar, hesap hareketleri.
- [ ] **Liste kendi içinde kaydırılabiliyor** (uzun listede tekerlek önce
      listeyi kaydırmalı, dibe gelince sayfayı).
- [ ] **Boş profil**: Aktif Borçlarım / Yaklaşan Ödemeler / Varlık Geçmişi
      kartları mesajları kadar yer kaplıyor, ekran dolusu boşluk yok.
- [ ] **Boş dönem**: Son İşlemler altında "Bu dönemde işlem bulunmuyor." yazıyor.
- [ ] **Dolu profil**: borç kartında iki satır tam görünüyor, son satır
      ortadan kesilmiyor.
- [ ] **Varlık sekmesi**: "Aktif Varlıklarım" ve "Varlık Geçmişi" kartları
      birbirinin üstüne binmiyor (satırlar kart sınırının dışına taşmıyor).
- [ ] **Başlık ikonları** yazıya binmiyor: Aktif Borçlarım, Yaklaşan Ödemeler,
      Bekleyen İşlemler, Varlık Geçmişi.

---

## 5. Yükseltme ve kaldırma

- [ ] Önceki sürümü kurup veri girin → RC-4'e **yükseltin** → veri duruyor mu?
- [ ] **Kaldırın** → kullanıcı verisi korunuyor mu (profil dizini silinmemeli),
      program dosyaları temizleniyor mu?
- [ ] **Yeniden kurun** → eski veri geri geliyor mu, anahtar hâlâ çözebiliyor mu?

---

## 6. Ortam matrisi

- [ ] Türkçe klavye: tutar alanlarına `1.234,56` yazımı, ı/İ/ğ/ş içeren
      açıklamalar kaydedilip geri okunuyor.
- [ ] %125 ve %150 DPI: metin kırpılmıyor, ikon/başlık hizaları bozulmuyor
      (bu turda düzeltilen kusur tam olarak buydu).
- [ ] Çoklu monitör: pencere ikinci ekrana taşındığında ölçek bozulmuyor.

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
