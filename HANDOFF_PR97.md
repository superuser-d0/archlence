# Devir Notu — PR #97 arayüz düzeltmeleri ve Windows RC turu

**Tarih:** 2026-08-13 · **Dal:** `fix/dashboard-scroll-and-empty-cards`
· **HEAD:** `5671859` · **PR:** [#97](https://github.com/superuser-d0/archlence/pull/97)
· **Taban:** `fix/monetary-boundaries-and-record-integrity` ([#95](https://github.com/superuser-d0/archlence/pull/95), DRAFT)

Bu dosya işi başka bir makineden sürdürebilmek içindir. Tur bitip #97 merge
edildiğinde silinebilir — `HANDOFF_RC_WINDOWS.md` ile birlikte.

---

## 0. EN ÖNEMLİ MADDE — SIRA #95 → #97

#97'nin tabanı `main` DEĞİL, #95'in dalı. GitHub `MERGEABLE` diyor; buna bakıp
merge etmek yanlış olur. #95 hâlâ draft ve fiziksel Windows turunu bekliyor
(`HANDOFF_RC_WINDOWS.md` §2). Önce o tur biter ve #95 merge edilir; #97'nin
tabanı o zaman kendiliğinden `main`'e döner.

**İkinci tuzak:** workflow'ların hepsi `pull_request: branches: [main]` ile
tetikleniyor. Tetikleyici PR'ın HEDEF dalına bakar, kaynağa değil — yani #97
`main`'i hedefleyene kadar **hiç check toplamaz**. Bu bir arıza değil; sinyal
istiyorsan elle tetikle:

```bash
gh workflow run tests.yml --ref fix/dashboard-scroll-and-empty-cards
gh workflow run build-windows.yml --ref fix/dashboard-scroll-and-empty-cards
gh workflow run build-linux.yml --ref fix/dashboard-scroll-and-empty-cards
```

---

## 1. Bu dalda ne var (4 commit)

| Commit | Konu |
|---|---|
| `d5c9b04` | Kart içi listelerin tekerleği yutması + boş kartların yer ayırması + başlık ikonlarının yazıya binmesi |
| `17adb2b` | `WINDOWS_RC_CHECKLIST.md` — devir notunun §2'sini işaretlenebilir listeye çevirir |
| `0888ccb` | "Kartlarım" şeridini sabit yüksekliğe geri alır (aşağıya bak) |
| `5671859` | "Algoritmik Öngörü" ikon düzeltmesi + kurulum turunun sonuçları |

Ayrıntı CHANGELOG'un `[Unreleased]` bölümünde ve commit mesajlarında. Burada
yalnızca **kodda görünmeyen** kararlar var.

### #95 ile birleştirilen çözüm

#95, tekerlek hatasını yalnız "Kartlarım" şeridi için `HorizontalStripScrollView`
ile kapatmıştı. O sınıf **kaldırıldı**; işini `ui/components.py::_WheelPassthroughMixin`
üzerinden `PassthroughScrollView` / `PassthroughRecycleView` devraldı — davranış
aynı (`do_scroll_y` kapalıysa dikey tekerlek sahiplenilmez), kapsam tüm kart içi
listeler. #95'in fiziksel makinede ölçtüğü kanıt mixin'in docstring'ine taşındı.
Sürükleme yolu #95'teki gibi `scroll_type: ["bars"]` ile kapalı kalıyor.

### Denenip ÖLÇÜLEREK geri alınan iki şey

Bunları tekrar denemeden önce buradaki ölçümü okuyun.

1. **"Kartlarım" şeridini içeriğe göre kısaltmak** (kart yokken 620dp boşluk
   kalmasın diye). Kaydırma kapısı bunu yakaladı: #95'in koşusunda
   `accounts_tab` içerik 1056dp / sürükleme ✓, bu bağlamayla 1031dp /
   **sürükleme ✗** — hem CI'da hem yerelde. Şerit kısalınca hesap kartları
   sürükleme noktasına geliyor ve `MDCard` dokunuşu yutuyor. Yani boş kartın
   yerini kazanmak, sekmenin kaydırılabilmesine mal oluyordu. Sabit 620dp'ye
   döndürüldü (`0888ccb`).

2. **Varlık geçmişi / son işlemler listelerinin yüksekliğini içerikten
   türetmek.** `RecycleView` satırlarını kendi yüksekliğine göre yerleştiriyor;
   yüksekliği satır sayısına ya da `RecycleBoxLayout.minimum_height`'a bağlamak
   döngü kuruyor ve döngü, satırların kartın DIŞINA — alttaki kartın üstüne —
   çizildiği bir boyutta çözülüyor. Ekran görüntüsüyle doğrulandı. Bu iki liste
   ikili duruma bağlandı: doluyken eski sabit yükseklik, boşken kapalı.

### Kaydırma kapısındaki bilinen tutarsızlık

`scripts/dev/verify_tab_scrolling.py` **boş profille** yeşil (CI de böyle
koşuyor). **Dolu profille** `accounts_tab` sürüklemesi kırmızı — #95'in kendi
ucunda da öyle. Muhtemel sebep, devir notunda zaten "bilinen sınır" diye yazılı
olan `MDCard` dokunuş yutması: kart sayısı arttıkça sürükleme noktası bir kartın
üzerine denk geliyor. Fiziksel turda dolu profille elle sürükleyip hangisi
olduğunu ölçün; kapı sonuca göre düzeltilmeli.

---

## 2. Test edilecek yapı (RC-5)

```
Source commit : 5671859b576f0b2e8caf1e6c5030f008381d58d3
Workflow run  : 31679532152  (Build Windows EXE, yeşil, head_sha eşleşiyor)
Artifact      : Archlence-Setup -> ArchlenceSetup.exe
Boyut         : 55.174.507 bayt
SHA-256       : 1c976b33d72dc119e24a824ce09079d29dcc529ecbff0387e540292bf29ee722
```

```bash
gh run download 31679532152 --repo superuser-d0/archlence \
  --name Archlence-Setup --dir rc5
```

Eski yapıları kullanmayın: `3a64aafd…` (RC-3), `02b334b3…` (RC-4). RC-4'te ikon
düzeltmesi, RC-3'te ise #97'nin tamamı yok.

---

## 3. Turun nerede kaldığı

`WINDOWS_RC_CHECKLIST.md` işaretlenmiş hâliyle depoda. Özet:

**Ölçüldü (RC-4, temiz profil, Windows 11 Pro 26200):**
- SmartScreen/Defender uyarısı çıkmadı.
- Yönetici istemi çıkmadı; kurulum kullanıcı başına.
- Profil `%LOCALAPPDATA%\Archlence` altında oluştu.
- Dizinde yalnız `encryption.key.dpapi` var, düz `encryption.key` **yok** —
  anahtar doğrudan DPAPI'ye yazılmış. §3'ün ön koşulu sağlandı.
- **Bulunan hata:** "Algoritmik Öngörü" ikonu metne biniyordu → `5671859` ile
  düzeltildi, RC-5'te doğrulanacak.

**Açık, sırayla:**
1. Restore dosya seçicisi (§2.1) — #95'in asıl testi, hiç ölçülmedi.
2. Kartlarım kaydırma (§2.2) — tekerlek + sürükleme, dolu profille.
3. **Reboot sonrası DPAPI (§3)** — üç turdur devrediyor; şifreli veriye erişimi
   kaybettirebilecek tek senaryo.
4. #97'nin arayüz maddeleri (§4), ikon düzeltmesi dahil.
5. Upgrade → uninstall → reinstall (§5).
6. Türkçe klavye / %125-150 DPI / çoklu monitör (§6).

---

## 4. Yerel durum

- Suite: **930 test, OK** (12 skip) — `5671859` üzerinde.
- Elle tetiklenen son koşular yeşil: Tests `31677456572`, Build Windows
  `31679532152`, Build Linux `31675940152`.
- Çalışma ağacı temiz, HEAD `origin` ile aynı. Diğer makinede:
  `git fetch origin && git checkout fix/dashboard-scroll-and-empty-cards`

Sorun çıkarsa ilk bakılacak yer: `%LOCALAPPDATA%\Archlence\Logs\crash.log`
