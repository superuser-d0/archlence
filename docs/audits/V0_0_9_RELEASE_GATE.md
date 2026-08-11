# v0.0.9 Release Gate

Denetim commit'i: `d5bd35f` · Tarih: 2026-08-06

---

## P0 release blocker

**Yok.** Bu denetimde kullanıcı verisini bozan, yanlış bakiye üreten veya
kurtarmayı engelleyen bir bulgu tespit edilmedi.

> Bu, "P0 yok" değil **"denetlenen alanlarda P0 bulunmadı"** anlamına gelir.
> Denetlenmeyen alanların listesi `V0_0_9_DEEP_AUDIT.md` bölüm 9'dadır.

---

## P1 release blocker

| ID | Bulgu | Neden blocker |
|---|---|---|
| A-1 | İstisna kapısı `except (Exception,)`, `except builtins.Exception` ve alias biçimlerini görmüyor | Kapı, geniş-handler borcunu büyütmeme sözünün tek mekanizması; üç biçimle tamamen atlanabiliyor |
| A-2 | Kapı baseline slack'ini hiç kontrol etmiyor; handler daraltmak sessizce ücretsiz slot açıyor | v0.0.6'daki 44-slot durumunun mekanizması aynen duruyor, kendiliğinden tekrarlayabilir |
| A-3 | Taksit aylık tutarının quantization'ı hiçbir test tarafından korunmuyor (assertion totolojik) | v0.0.8'de düzeltilen para hatasının regresyon koruması fiilen yok |

Üçü de **kalite kapısı** kusuru. Bugünkü kullanıcı verisini bozmuyorlar; gelecek
kusurların fark edilmeden geçmesine izin veriyorlar.

---

## Zorunlu otomatik testler (v0.0.9 öncesi eklenecek)

- [ ] `scripts/audit_exception_handlers.py` için test dosyası:
      - [ ] `except (Exception,)` sayılıyor
      - [ ] `except (Exception, OSError)` sayılıyor
      - [ ] `except builtins.Exception` sayılıyor
      - [ ] `X = Exception; except X` sayılıyor
      - [ ] baseline gerçekten azaldığında kapı kırılıyor
      - [ ] slack'e sızan yeni handler kırılıyor
- [ ] Taksit toplamı testi gerçek toplama bağlanıyor (totoloji kaldırılıyor)
- [ ] Yarım-kuruş ayrışma vakası test vakası olarak ekleniyor
      (`100,01 / 2`, `100,02 / 12`)
- [ ] Yukarıdaki her yeni test mutation ile doğrulanıyor: davranış bozulunca
      kırmızı, geri alınınca yeşil

---

## Zorunlu manuel testler

- [ ] Temiz kurulumda ilk açılış ve ilk hesap
- [ ] v0.0.8 profilinden yükseltme, veri korunumu
- [ ] Yedek alma ve geri yükleme, öncesi/sonrası toplam karşılaştırması

---

## Windows gerçek donanım kontrol listesi

**Bu maddeler CI ile kapatılamaz.** Gerçek Windows makinesi olmadan hiçbiri
"geçti" sayılamaz.

- [ ] DPAPI ile anahtar saklama ve okuma
- [ ] OS keystore erişimi reddedildiğinde davranış
- [ ] Kurtarma akışı uçtan uca
- [ ] SmartScreen uyarısı ve kullanıcı deneyimi
- [ ] Antivirüs karantinası / dosya kilidi
- [ ] Kurulum, yükseltme, kaldırma, yeniden kurulum
- [ ] Uygulama açıkken yükseltme başlatma
- [ ] Unicode ve boşluk içeren kurulum yolu
- [ ] %125 / %150 / %200 DPI ölçeklendirme
- [ ] `crash.log` konumu ve içeriği

---

## Yedekleme / geri yükleme kontrol listesi

Bu denetimde **kapsanmadı**; v0.0.9 öncesi en az temel akış doğrulanmalı.

- [ ] Boş profil turu
- [ ] Bir yıllık demo profil turu
- [ ] Yanlış parola reddi
- [ ] Bozulmuş arşiv reddi
- [ ] Geri yükleme başarısızlığında mevcut verinin bozulmaması
- [ ] Geri yükleme sonrası finansal toplamların değişmemesi

---

## Migration kontrol listesi

- [x] v0.0.1 → current (bakiye, işlem sayısı, şifreli alan korundu)
- [x] v0.0.4 → current
- [x] v0.0.6 → current
- [x] Migration idempotent
- [ ] Dolu/gerçekçi eski profil (kart, borç, abonelik, varlık) ile tur
- [ ] Migration yarıda kesilirse rollback / kurtarma
- [ ] `user_version` işareti ve downgrade koruması

---

## Finansal değişmez kontrol listesi

- [x] Taksitlerin kalan borcu anaparadan türetiliyor
- [x] Varlık alım/satım nakit tutarı kuruşa yuvarlanıyor
- [x] Borç tutarları saklanırken yuvarlanıyor
- [x] Borç toplamı = aylık × vade
- [x] Karar eşikleri (limit, çekim, hedef) kuruş hassasiyetinde
- [x] Her bakiye değişimi ledger event yazıyor
- [ ] Taksit aylık tutarı quantization'ı **korunmuyor** (A-3)
- [ ] Tekrarlayan ödeme idempotency'si denetlenmedi
- [ ] Çift tıklama / retry senaryoları denetlenmedi

---

## Paketleme kontrol listesi

- [x] Sürüm tutarlılığı kapısı geçiyor (`0.0.8 / tag v0.0.8`)
- [ ] `PKGBUILD` hash'leri yayın sonrası dolduruluyor (her sürümde tekrar eden adım)
- [ ] Windows installer smoke testleri gerçek donanımda
- [ ] AppImage FUSE ve extract-and-run

---

## Soak kontrol listesi

- [ ] En az 3 gün RC, günlük kullanım
- [ ] Crash, unhandled exception, DB lock kaydı
- [ ] Bellek / thread / bağlantı artışı gözlemi
- [ ] Finansal toplamların gün başı–gün sonu tutarlılığı

---

## Go / No-Go karar kuralları

**GO koşulları (hepsi sağlanmalı)**

1. A-1, A-2, A-3 düzeltilmiş ve her biri mutation ile doğrulanmış.
2. Tam test suite yeşil, bloklayan lint 0, istisna kapısı yeşil.
3. Migration kontrol listesindeki işaretli maddeler hâlâ geçiyor.
4. CHANGELOG `## Unreleased` bölümü güncel ve yayınlanmamış her değişikliği
   içeriyor.
5. `PKGBUILD` hash'leri yayın sonrası doldurulmuş.

**NO-GO koşulları (herhangi biri)**

1. Yeni bir P0 bulgusu.
2. Soak sırasında finansal değişmez ihlali, çift işlem veya veri kaybı.
3. Migration turlarından herhangi birinde veri değişimi.
4. Yeni eklenen bir regresyon testinin mutation ile doğrulanamaması.

**Stable'a geçiş için ek koşul**

Windows gerçek donanım listesi kapatılmadan ve en az bir soak dönemi
tamamlanmadan "stable" etiketi kullanılmamalı. Bu denetim o alanları
**kapsamadı** ve simülasyon kanıt sayılmaz.
