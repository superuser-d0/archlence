# Devir Notu — PR #95 Windows RC doğrulaması

**Tarih:** 2026-08-13 · **Dal:** `fix/monetary-boundaries-and-record-integrity`
· **HEAD:** `3c1cd7c` · **PR:** [#95](https://github.com/superuser-d0/archlence/pull/95) (DRAFT)

Bu dosya, işi iki farklı makineden sürdürebilmek içindir. Doğrulama turu
bitip PR merge edildiğinde silinebilir.

---

## 0. EN ÖNEMLİ MADDE — BU PR'I MERGE ETME

PR bilerek **draft**. Bütün CI kontrolleri yeşil ve `mergeStateStatus` `CLEAN`
görünüyor; buna bakıp merge etmek YANLIŞ olur. Nedeni CI'da görünmüyor:

> İçindeki iki düzeltme, **fiziksel bir Windows makinesinde bildirilen**
> hatalara ait ve **o makinede henüz yeniden test edilmediler.**

Merge kararı, aşağıdaki §2 listesi gerçek donanımda koşulduktan sonra
**depo sahibinindir**. Testler geçerse PR `gh pr ready 95` ile draft'tan
çıkarılır.

---

## 1. Bu dalda ne var

İki turluk finansal denetim + gerçek makineden gelen iki hata düzeltmesi.
Ayrıntı CHANGELOG'un `[Unreleased]` bölümünde ve commit mesajlarında; burada
yalnızca **kodda görünmeyen** kararlar var.

### Gerçek makineden gelen düzeltmeler (bu turun konusu)

| Bulgu | Kök neden | Düzeltme |
|---|---|---|
| Restore dosya seçicisi uygulamanın tamamını çökertiyordu | Kivy `win32file.GetFileAttributesExW` çağırıyor; pywin32 o çağrının İÇİNDE `win32timezone`'u import ediyor, PyInstaller statik analizi göremiyor | `archlence.spec` → `hiddenimports` |
| "Kartlarım" sekmesi hiç kaydırılamıyordu | Sayfanın dikey ScrollView'ı içindeki yatay kart şeridi (620dp, görünür alandan büyük) her dokunuşu sahipleniyor; Kivy iç içe ScrollView'da dokunuşu ÖNCE çocuğa soruyor | `ui/dashboard.kv` → şeride `scroll_type: ["bars"]` (sürükleme) **+** `ui/components.py` → `HorizontalStripScrollView` (tekerlek) |
| Kullanıcı kendi yedeğine geri yükleme seçicisinden ulaşamıyordu | Yedekler `data_dir()/backups` altında, Windows'ta gizli `AppData`nın içinde; seçici ev dizininde açılıyor ve Kivy gizli girdileri listelemiyor | `mixins/migration_mixin.py` → `restore_chooser_path()` |

### Ölçülen öncesi/sonrası (Kartlarım, sayfa tepedeyken)

```
                          ÖNCESİ    1. DÜZELTME   2. DÜZELTME
sürükleme (aşağı)         ölü       çalışıyor     çalışıyor
tekerlek (scrollup)       ölü       ÖLÜ           çalışıyor
```

`scroll_type: ["bars"]` yalnız sürüklemeyi kurtardı; tekerlek ikinci turda
fiziksel makinede hâlâ ölü bulundu ve `HorizontalStripScrollView` ile
kapatıldı. Ölçüm kapısı da düzeltildi: `scrolldown` yerine `scrollup`
kullanıyor (ilki sayfa tepedeyken Kivy tarafından zaten reddediliyor, yani
sağlam ve bozuk sekmeyi ayırt etmiyordu) ve tekerleği sürüklemeden ÖNCE
ölçüyor (sürüklemenin bıraktığı efekt artığı sahte yeşil üretiyordu).

### BİLİNEN SINIR — hata değil, davranış

Doğrudan bir **kartın üzerinden** sürüklemek sayfayı kaydırmaz: KivyMD'nin
`MDCard`'ı `on_touch_down`'ı sahiplenip `True` dönüyor (ölçüldü:
`PremiumCreditCardWidget`). Bu, uygulama genelinde geçerli çerçeve davranışı ve
bu düzeltmenin getirdiği bir şey DEĞİL. Kartların üzerinde **tekerlek çalışıyor**.
Yeni bir hata raporu bunu tekrar bildirirse "zaten biliniyor" diye kapatmayın;
düzeltmek KivyMD kart davranışına dokunmayı gerektirir, ayrı bir iştir.

> **DÜZELTME (2026-08-13, ikinci fiziksel tur).** Bu bölümün ilk hâli
> davranışı TERS anlatıyordu: "sürükleme çalışmaz, tekerlek çalışır" deniyordu.
> Fiziksel testte tam tersi ölçüldü — sürükleme çalışıyordu, **tekerlek
> ölüydü**. Sebep, ilk düzeltmenin (`scroll_type: ["bars"]`) yalnızca sürükleme
> yolunu kapatması; Kivy'nin tekerlek dalı `bars` kapısından ÖNCE çalışıyor ve
> hiçbir şey kaydıramasa bile olayı yutuyor. Tekerlek yolu ayrıca
> `HorizontalStripScrollView` ile kapatıldı (bkz. `ui/components.py`).
> Yukarıdaki paragrafın kart/sürükleme kısmı geçerliliğini koruyor.

---

## 2. AÇIK — yalnızca gerçek Windows makinesi doğrulayabilir

Hiçbiri CI'da ölçülmedi. **"Windows integration verified" DEMEYİN.**

Öncelik sırasıyla:

1. **Restore'u aç** (Ayarlar → Geri Yükle → dosya seçici). Çökmemeli.
   Bu turun asıl testi.
2. **Kartlarım'ı kaydır** — tekerlek ve sürükleme (yukarıdaki bilinen sınırı
   akılda tutarak).
3. **Reboot sonrası DPAPI** — şifreli veri yeniden açılıyor mu. Bir önceki
   turdan devrediyor, hâlâ yapılmadı.
4. SmartScreen / Microsoft Defender davranışı (installer imzasız).
5. Standart (yönetici olmayan) kullanıcıyla kurulum.
6. Upgrade → uninstall → reinstall zinciri, kullanıcı verisinin korunması.
7. Türkçe klavye, %125 / %150 DPI, çoklu monitör.

Sorun çıkarsa ilk bakılacak yer: `%LOCALAPPDATA%\Archlence\log\crash.log`

---

## 3. Test edilecek yapı

```
Source commit : 02d27d2b805d4f61ce112e266d0dfa7ded7d29a2   (RC-3)
Workflow run  : 31657595641  (Build Windows EXE, head_sha eşleşiyor)
Artifact      : Archlence-Setup -> ArchlenceSetup.exe
Boyut         : 55.176.805 bayt
SHA-256       : 3a64aafd44ffc426e8bd51ed72c3f6a35d0aaced1f7c7a8ca349e9bc226135a8
```

İndirme (release YOK, yayın yapılmadı — artifact 2026-11-11'e kadar duruyor):

```bash
gh run download 31657595641 --repo superuser-d0/archlence \
  --name Archlence-Setup --dir rc-audit-pr95
```

**ESKİ RC'LERİ KULLANMAYIN — ikisi de aşıldı:**

| Hash | Neden geçersiz |
|---|---|
| `151506a3…24d53` | Restore dosya seçicisi uygulamayı çökertiyor |
| `094ead55…4a56` | Kartlarım tekerleği ölü + yedekler seçiciden görünmüyor |

Diskte kalmışlarsa silin.

---

## 4. Bu turda öğrenilen ders — tekrarlamayın

Bu turda CI/doğrulama kodu **dört kez** hatalı çıktı. Üçü de uygulama kodunu
değil doğrulama katmanını etkiledi, ama örüntü aynı: **Linux'tan Windows
paketleme/çalışma davranışı hakkında varsayım yapmak.**

1. Kaydırma regresyon kapısının ilk hâli ara bir kaydırma konumundan ölçüyordu
   ve **düzeltme geri alındığında da yeşil kalıyordu** — yani hatayı hiç
   yakalamıyordu. Arıza sayfanın TEPESİNDEydi.
2. Paketleme kontrolü `shell: pwsh` altında bash heredoc kullanıyordu;
   PowerShell ayrıştırma hatası verdi.
3. Paketleme kontrolü yalnızca `.exe`'yi bayt bazında tarıyordu. `win32file`
   bir `.pyd`, yani **diskte ayrı bir dosya** — exe'nin içinde değil. Kontrol
   ebeveyni hiç göremediği için koşulu tetiklenmiyor, **gerçekte çöken yapıyı
   sessizce geçiriyordu.**

4. Kaydırma kapısı tekerleği `scrolldown` ile deniyordu — sayfa tepedeyken
   Kivy'nin HER ScrollView'da reddettiği yön, yani sağlam ve bozuk sekmede
   aynı sonucu veren, ayırt etmeyen bir ölçüm. Üstelik ölçüm sürüklemeden
   sonra koşuyordu ve sürüklemenin bıraktığı efekt artığı `scroll_y`'yi
   1.000'den azıcık kaydırıp o reddi devre dışı bırakıyordu: kapı, gerçekte
   ölü olan tekerleği **çalışıyor sanıyordu**. Fiziksel makine yakaladı.

**Kural:** bir kapı yazdıysanız, onu **bilinen-bozuk bir yapıya karşı**
çalıştırıp kırmızıya döndüğünü görün — ve düzeltmeyi geri alıp gerçekten
kızardığını teyit edin. Üçüncü madde çöken RC'nin artifact'ı indirilip kontrol
ona karşı koşularak bulundu (`EXIT=1`); dördüncüsü ancak fiziksel makinede
görüldü, çünkü kapı kendi ölçüm yöntemiyle kendini kandırıyordu.

---

## 5. Kapılar nerede

| Kapı | Yer | Ne ölçüyor |
|---|---|---|
| Sekme kaydırma | `scripts/dev/verify_tab_scrolling.py` (visual-regression job, 4 DPI/dil) | Gerçek olay döngüsünden dokunuş gönderip `scroll_y` değişiyor mu |
| Paketleme bütünlüğü | `scripts/check_frozen_lazy_imports.py` (build-windows job) | Paketlenmiş modül, çağrı anında import ettiği eşlikçiyi de getirmiş mi |
| Para sınırları | `tests/test_monetary_boundary_invariants.py` | 20 para sınırı `nan`/`inf`/`-inf` reddediyor + hiçbir tabloya yazmıyor |
| Windows sözleşmeleri | `tests/test_windows_platform_contracts.py` | Gerçek DPAPI (yalnız Windows), ASCII dışı/uzun yol, anahtar yarışı |

---

## 6. İki makineyle çalışma kuralları

- Bu dala **force-push yapılmadı ve yapılmamalı** — geçmiş sabit, iki taraf da
  güvenle `pull --rebase` alabilir.
- İşlem yapmadan önce `git fetch origin` — karşı taraf commit atmış olabilir.
- Depo dışındaki `rc-audit-pr95/` klasörü **senkronize DEĞİL** (53 MB ikili,
  `.gitignore` zaten `dist/`, `*.exe` koruyor). §3'teki komutla her makinede
  yeniden üretin, kopyalamayın.
