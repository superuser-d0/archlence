# v0.0.9 Phase 3 — Durum

**Dal:** `fix/v0.0.9-reliability` · **Taban:** `d5bd35f`
**Status: Phase 3 completed with explicit environment limitations**
**RC kararı: RC GO — pending Windows validation**

## Kapanan blocker'lar

| Alan | Status | Commit |
|---|---|---|
| P0-1 … P0-7 | **Closed** | Phase 3 ilk turu |
| P1-1 restore generation | **Closed** — görsel doğrulama beklemede | `05da34a` `616224f` `efadc1c` `6bb7a4f` |
| P1-2 migration retry | **Closed** | `652d512` |
| A-1 / A-2 istisna kapısı | **Closed** | `6877dd5` |
| Fault injection güvenilirliği | **Closed** | `493dd3c` |
| Connection cleanup (P2-7) | **Closed — bulgu yanlış atfedilmişti**; kök neden denetim probe'unun kendi sızıntısı, üretimde düzeltme gerekmedi. Ayrı bir üretim eksiği (`initialize_database` try/finally) aynı incelemede bulunup düzeltildi | harness `28e43f0`, regresyon `94db19f` + `28e43f0`, üretim düzeltmesi `dac9a15` — ayrıntı `V0_0_9_PRE_WINDOWS_GATE.md` §3–§5 |
| Windows `0.0.1` fallback | **Closed** | `ddda5ed` |
| Upgrade previous-release | **Closed** — runtime doğrulanmadı | `ddda5ed` |
| P2 asset açıklama | **Closed** | `8b1744e` |
| Version 16-mutation matrisi | **Closed** — 16/16 | `5d05084` `1223935` |
| Supply-chain pinning | **Closed** | `1223935` |
| Reliability CI job'ı | **Closed** — job gerçek, kaçış kapısı yok | `ad6296f` |
| Reliability CI'ın ZORUNLU olması | **Açık — repo ayarı.** Branch protection yalnız `build-windows` ve `test` istiyor; `reliability-gates` ve `test-windows` merge'ü bloklamıyor | kod değişikliği yok — `V0_0_9_PRE_WINDOWS_GATE.md` §8 |

## Blocked by environment

| Alan | Neden |
|---|---|
| Gerçek Windows doğrulaması | DPAPI, SmartScreen, installer upgrade/uninstall, DPI |
| Görsel recovery dialog rendering | dummy window provider; orchestration doğrulandı |
| Gerçek AppImage build/smoke | CI'da koşacak, yerelde çalıştırılmadı |

## Açık (release blocker DEĞİL)

| İş | Sınıf |
|---|---|
| `user_version` şema işareti (A-5) | P3 |
| Pyflakes backlog (109) | P3 |
| Geniş exception borcu (145) | P3 — kapı sağlam, borç büyümüyor |

## Doğrulama

```
normal suite         796 test OK (skip 2)   ← Phase 3 kapanışında 781
reliability-gates    16/16 version mutation · migration matrisi · 21 adversarial · property
bloklayan lint       0
istisna kapısı       145 handler yeşil
sürüm kapısı         0.0.8 / tag v0.0.8
compileall           temiz
git diff --check     temiz
```

## Commit zinciri

Denetim izinin eksiksiz olması için Phase 3'ün tamamı kronolojik sırada.
Taban `d5bd35f` (origin/main). Tur 1–4 Phase 3'ün kendisi (32 commit,
`d5bd35f..2bd5f0d`); Tur 5 Windows öncesi doğrulama turu.

### Tur 1 — denetim ve P0 kapanışları (`d5bd35f..2212e10`)

| Commit | Konu |
|---|---|
| `5302d1a` | audit: v0.0.9 öncesi derin kalite denetimi |
| `c57549e` | test: complete v0.0.9 phase 2 reliability audit |
| `4eb0160` | test: finish v0.0.9 phase 2 reliability audit |
| `998584e` | fix: reject non-finite financial values |
| `b9e5736` | fix: make recurring operations idempotent |
| `467b269` | fix: serialize credit-card limit checks |
| `dfec949` | docs: record v0.0.9 phase 3 baseline |
| `96049ee` | fix: make asset sales atomic |
| `df46a31` | fix: make debt payments atomic |
| `0368853` | fix: authenticate backup packages |
| `3fccc8e` | fix: reject unexpected backup archive members |
| `c2ae4c1` | fix: secure plaintext CSV exports |
| `bfb2b37` | test: restore regression coverage lost to the atomicity refactor |
| `2212e10` | docs: record v0.0.9 phase 3 continuation point |

### Tur 2 — P1 kapanışları (`2212e10..ac67447`)

| Commit | Konu |
|---|---|
| `05da34a` | fix: make profile restore atomic |
| `652d512` | fix: make database migrations retry safe |
| `6877dd5` | test: harden exception quality gate |
| `30607a3` | docs: update phase 3 continuation after P1 closures |
| `616224f` | fix: recover interrupted restores during startup |
| `493dd3c` | test: verify financial fault injections reach production paths |
| `02e09b5` | docs: correct P1-1 status and add phase 3 reports |
| `efadc1c` | fix: complete committed restore recovery |
| `6bb7a4f` | fix: present restore recovery failures safely |
| `ac67447` | docs: record P1-1 closure with environment limitation |

### Tur 3 — `ac67447..3cdff27` (önceki raporda listelenmemişti)

| Commit | Konu | Kapattığı madde |
|---|---|---|
| `94db19f` | test: pin deterministic database connection cleanup | Connection cleanup — `tests/test_connection_cleanup.py` (yalnız test; üretim davranışı zaten doğruydu, delta 0 sabitlendi) |
| `ddda5ed` | test: harden release and packaging gates | Windows `0.0.1` fallback + upgrade previous-release seçimi — `scripts/previous_release.py`, `.github/workflows/build-windows.yml`, `tests/test_previous_release_selection.py` |
| `8b1744e` | fix: preserve asset transaction descriptions | P2-6 asset açıklama — `services/asset_sale_service.py`, `tests/test_asset_sale_cash_amount.py` |
| `3cdff27` | docs: complete v0.0.9 phase 3 reliability report | CHANGELOG + Phase 3 raporu |

### Tur 4 — `3cdff27..2bd5f0d` (kapanış turu)

| Commit | Konu | Kapattığı madde |
|---|---|---|
| `5d05084` | test: harden version consistency gate | 16-mutation matrisinin kendisi — `scripts/audit/version_mutation_matrix.py`, `scripts/check_version_consistency.py` |
| `1223935` | ci: pin packaging tools and actions | Supply-chain pinning + matris düzeltmesi — 4 workflow |
| `ad6296f` | test: promote reliability regressions into CI | `reliability-gates` job'ı — `requirements-dev.txt` (job'ın ZORUNLU olması ayrı mesele, yukarıdaki tabloya bkz.) |
| `2bd5f0d` | docs: record phase 3 completion and RC decision | Phase 3 kapanış kararı |

### Tur 5 — Windows öncesi doğrulama turu

| Commit | Konu | Kapattığı madde |
|---|---|---|
| `3551049` | docs: complete phase 3 commit traceability | Tur 3 ve Tur 4'ün rapordaki boşluğu |
| `dac9a15` | fix: close database connections deterministically | `initialize_database()` hata yolunda bağlantı bırakıyordu — `database/init_db.py` |
| `28e43f0` | test: correct connection cleanup regression harness | P2-7'nin yanlış atfı; denetim probe'unun kendi sızıntısı (13 site) + 15 sahiplik testi |
| *(bu commit)* | docs: finalize pre-Windows release traceability | `V0_0_9_PRE_WINDOWS_GATE.md` + statü düzeltmeleri |

### İzlenebilirlik notu

Önceki rapor turu `ac67447` HEAD'inde yazılmıştı; kapanış raporu `3cdff27`
tabanlıydı. Tur 3 ve Tur 4 tabloları bu iki boşluğu kapatır. Tur 5 ise
Phase 3'ün kendisi değil, Windows'a geçmeden önce kalan teknik
belirsizlikleri kapatan doğrulama turudur.

## Sonraki adım

Phase 3 sonrası bir doğrulama turu daha koşuldu (`V0_0_9_PRE_WINDOWS_GATE.md`):
connection cleanup bulgusu kesinleştirildi, bir üretim eksiği düzeltildi,
statü atıfları denetlendi. Karar **PRE-WINDOWS GO**.

**Sırada: gerçek Windows doğrulaması.** Bu olmadan final release GO verilemez.
Kontrol listesi `V0_0_9_PHASE_3_RELEASE_GATE.md` içinde.

Push/PR/tag/release YOK. Sürüm bump YOK.
