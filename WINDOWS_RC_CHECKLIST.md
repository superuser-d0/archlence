# Windows donanım doğrulama — kontrol listesi (RC-4 adayı)

Kaynak: `HANDOFF_RC_WINDOWS.md` §2 + PR #97 ile gelen arayüz değişiklikleri.
Amaç, "Windows integration verified" cümlesini kurabilmek için gereken
ölçümleri tek yerde toplamak.

---

## 0. Hangi yapı test edilecek

RC-3 (`02d27d2`, SHA-256 `3a64aafd…35a8`) **yetmez**: PR #97'nin arayüz
değişiklikleri o yapının içinde yok. Doğrulanacak aday, #95 + #97'nin
birleşimi — yani `fix/dashboard-scroll-and-empty-cards` dalının ucu (`d5c9b04`).

Aday derleme, o dalda elle tetiklenen `workflow_dispatch` koşusudur —
`31675937556` (Build Windows EXE). Bu koşu **yeşil değilse** aşağıdaki hiçbir
madde ölçülmez.

```bash
gh run download 31675937556 --repo superuser-d0/archlence \
  --name Archlence-Setup --dir rc4
certutil -hashfile rc4\ArchlenceSetup.exe SHA256
```

- [ ] Koşu yeşil mi — `gh run view 31675937556 --json conclusion`
- [ ] `head_sha` gerçekten `d5c9b04` mü — `gh run view 31675937556 --json headSha`
- [ ] İndirilen dosyanın SHA-256'sı not edildi: `________________________`
- [ ] Eski RC'ler (`151506a3…`, `094ead55…`, `3a64aafd…`) diskten silindi

> Yapı yeşil değilse durun. Kırmızı bir yapıyı fiziksel makinede test etmek,
> ölçtüğünüz şeyin ne olduğunu bilmemek demektir.

---

## 1. Kurulum ve ilk açılış

- [ ] **SmartScreen / Defender.** Kurulum imzasız; uyarı çıkıyor mu, hangi
      metinle, "yine de çalıştır" ile geçiliyor mu? Ekran görüntüsü alın —
      README'deki "SmartScreen may warn" ifadesinin gerçekten karşılığı bu mu?
- [ ] **Yönetici olmayan kullanıcı.** Standart bir hesapla kurun. Kurulum
      kullanıcı başına; yönetici istemi ÇIKMAMALI.
- [ ] **İlk açılış.** Uygulama açılıyor, PIN/parola kurulumu tamamlanıyor.
- [ ] Profil dizini gerçekten `%LOCALAPPDATA%\Archlence` altında oluştu
      (kurulum dizininde veri YOK — ROADMAP Faz 1 madde 4).

---

## 2. #95'in bildirdiği iki hata (bu turun asıl konusu)

### 2.1 Restore dosya seçicisi — uygulamayı çökertiyordu

- [ ] Ayarlar → Geri Yükle → dosya seçiciyi aç. **Uygulama kapanmamalı.**
- [ ] Seçici bir klasörün içeriğini listeleyebiliyor (çökme ilk listelemede
      oluyordu).
- [ ] Kendi yedeğinize seçiciden ulaşabiliyor musunuz — `data_dir()/backups`
      altındaki dosyalar görünüyor mu? (Gizli `AppData` içindeler; seçici artık
      oraya açılmalı.)
- [ ] Bir yedeği gerçekten geri yükleyin ve verinin döndüğünü doğrulayın.

### 2.2 "Kartlarım" sekmesi kaydırma

Sayfa **tepedeyken** ölçün; ara konumdan ölçmek bu hatayı gizliyor (§4, ders 1).

- [ ] **Tekerlek**, kart şeridinin üzerindeyken sayfa aşağı iniyor
      ("Hesaplarım" bölümüne ulaşılabiliyor).
- [ ] **Tekerlek**, kartların altındaki boş alanda da çalışıyor.
- [ ] **Sürükleme**, şeridin kaydırma çubuğundan yatay olarak kartları
      kaydırıyor.
- [ ] **Sürükleme**, şeridin boş alanından dikey olarak sayfayı kaydırıyor.

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
