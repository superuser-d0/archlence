# v0.0.9 Phase 3 — Release Gate

Phase 3 teknik final: `2bd5f0d` · Taban: `d5bd35f` · 32 commit
Tam commit zinciri: `V0_0_9_PHASE_3_CONTINUATION.md` → "Commit zinciri"
Phase 3 SONRASI doğrulama turu ve güncel statü:
`V0_0_9_PRE_WINDOWS_GATE.md` (karar: **PRE-WINDOWS GO**)

## Karar: **RC GO — pending Windows validation**

Bütün P0'lar, P1'ler ve release-blocker P2'ler Closed. Kalan tek engel
GERÇEK WINDOWS DOĞRULAMASI — bu ortamda yapılamaz ve simülasyon kanıt
sayılmaz. Bu yüzden karar `RC GO — pending Windows validation`;
**final release GO değil**.

## Blocker tablosu

| ID | Status | Neden hâlâ blocker |
|---|---|---|
| P0-1 … P0-7 | **Closed** | — |
| P1-1 restore generation | **Closed** — visual validation pending | finansal mekanizma kapandı; yalnızca gerçek widget rendering doğrulanmadı |
| P1-2 migration retry | **Closed** | — |
| A-1 / A-2 kapı | **Closed** | — |
| Connection cleanup (P2-7) | **Closed — yanlış atıf düzeltildi** | bulgu üretim kodunun değil denetim probe'unun sızıntısıydı; beş commit'te ölçüldü, taban ile HEAD aynı çıktı. Ayrı bulunan `initialize_database` eksiği `dac9a15` ile kapandı. Bkz. `V0_0_9_PRE_WINDOWS_GATE.md` §3–§5 |
| Version mutation matrisi | **Closed** | 16/16 yakalandı |
| Packaging/upgrade gate | **Closed** | fallback kaldırıldı, taban semver ile seçiliyor |
| P2-6 asset açıklama | **Closed** | miktar/fiyat/K-Z geri geldi |

## RC GO için kalan somut koşullar

- [x] Connection cleanup bounded, explicit GC'ye bağlı değil — sahiplik
      sözleşmesi ayrıca açma/kapama sayarak (FD'den bağımsız) kanıtlandı
- [x] 16 version mutation vakasının tamamı yakalanıyor
- [x] Windows workflow `0.0.1` fallback'inden kurtuldu
- [x] Upgrade smoke gerçek önceki sürümü seçiyor
- [x] P2-6 kapandı
- [x] Kalan reliability testleri `reliability-gates` job'ında ve gerçekten
      koşuyor (kaçış kapısı yok)
- [ ] **`reliability-gates` merge'ü BLOKLUYOR** — hayır. Branch protection
      yalnız `build-windows` ve `test` istiyor; `reliability-gates`,
      `test-windows`, `lint`, `visual-regression` zorunlu değil. Repo ayarı,
      kod değil. Bkz. `V0_0_9_PRE_WINDOWS_GATE.md` §8
- [x] CHANGELOG `## Unreleased` güncel
- [x] Gerçek Windows checklist hazır (aşağıda)
- [ ] **Gerçek Windows doğrulaması yapıldı** ← tek kalan

Gerçek Windows installer/DPAPI/upgrade doğrulanmadan **final release GO
verilmemeli**; en fazla `RC GO — pending Windows validation` mümkün, o da
yukarıdaki maddeler kapandıktan sonra.

## Windows manuel kontrol listesi (kapsanmadı)

- [ ] DPAPI anahtar saklama/okuma, keystore reddi
- [ ] Kurtarma akışı uçtan uca
- [ ] SmartScreen, antivirüs, dosya kilidi
- [ ] Kurulum / yükseltme / kaldırma / yeniden kurulum
- [ ] Uygulama açıkken yükseltme
- [ ] %125 / %150 / %200 DPI
- [ ] **Yarım restore sonrası gerçek açılış kurtarması**
