# v0.0.9 Phase 3 — Devam Noktası

**Dal:** `fix/v0.0.9-reliability` · **HEAD:** `6877dd5` · **Taban:** `d5bd35f`
**Status: Phase 3 fixes in progress, RC blocked**

## Bu turda kapanan blocker'lar

| Commit | Blocker | Kanıt |
|---|---|---|
| `bfb2b37` | (regresyon) | Suite kırmızıydı, 3 koruma sessizce devre dışıydı |
| `05da34a` | **P1-1** restore generation | 5 fault noktası, DB+key+config birlikte geri dönüyor |
| `652d512` | **P1-2** migration retry | `account_type_after_retry='credit_card'` (önce `None`) |
| `6877dd5` | **A-1 + A-2** istisna kapısı | 4 bypass biçimi + slack yakalanıyor |

## P0 kapanış tablosu

| ID | Status | Kanıt |
|---|---|---|
| P0-1 backup authenticity | **Closed** | reproduction PASS |
| P0-2 charge idempotency | **Closed** | reproduction PASS |
| P0-3 refund idempotency | **Closed** | reproduction PASS |
| P0-4 asset atomicity | **Closed** | 4 fault noktası, tam rollback |
| P0-5 debt atomicity | **Closed** | 3 fault noktası, tam rollback |
| P0-6 non-finite | **Closed** | reproduction + nonfinite matrisi |
| P0-7 kart limiti TOCTOU | **Closed** | concurrency testi |

## P1 kapanış tablosu

| ID | Status | Kalan sınır |
|---|---|---|
| P1-1 restore generation | **Closed** | `recover_interrupted_restore()` **açılışa bağlanmadı** |
| P1-2 migration retry | **Closed** | `user_version` hâlâ 0 (P3/A-5) |
| A-1 kapı bypass'ı | **Closed** | — |
| A-2 kapı slack'i | **Closed** | — |

## Açık işler (sözleşme sırasıyla)

| # | İş | Dosya / görev |
|---|---|---|
| 4 | Deterministic connection cleanup | `database/db.py::get_connection` — ownership tablosu, `contextlib.closing`, FD regression testi |
| 5 | Version consistency gate | `scripts/check_version_consistency.py` — 16 mutation matrisi (workflow fallback, asset adı, tag mismatch, README official version) |
| 6 | Packaging/upgrade gate | `.github/workflows/build-windows.yml` — `0.0.1` fallback'i kaldır; upgrade smoke gerçek önceki sürümü seçsin |
| 6b | Supply-chain | Actions'ı immutable SHA'ya pinle |
| 7 | CI promotion | Kalan audit testlerini `tests/` altına veya zorunlu ayrı CI job'a |
| 8 | **P2-6** asset açıklama regresyonu | `services/asset_sale_service.py` — miktar/birim fiyat/K-Z açıklamaya geri |
| 9 | Dokümantasyon | CHANGELOG `## Unreleased`, `docs/SECURITY_RELIABILITY_STATUS.md`, Phase 3 rapor/matris/gate belgeleri |
| 10 | RC kararı | Yukarısı bitince |

## Bir sonraki oturumun ilk adımı

`recover_interrupted_restore()` çağrısını uygulama açılışına bağla
(`main.py` başlangıç akışı veya `database/init_db.py` öncesi). Şu an fonksiyon
var ve test ediliyor ama **hiçbir üretim yolu onu çağırmıyor** — yarım restore
otomatik toparlanmıyor.

## Doğrulama durumu

```
normal suite      733 test OK (skip 2)   ← tur başında 703, +30
bloklayan lint    0
istisna kapısı    145 handler yeşil
sürüm kapısı      0.0.8 / tag v0.0.8
adversarial       10/10 PASS
migration matrisi v0.0.1–v0.0.8 state/fresh_schema/idempotent hepsi True
git diff --check  temiz
```

## RC kararı: **NO-GO**

P0 ve P1'lerin hepsi kapandı, ama sözleşmenin RC GO koşulları arasında olan
connection cleanup, version mutation matrisi, upgrade smoke ve CI promotion
henüz yapılmadı. Gerçek Windows doğrulaması da yok.

Push/PR/tag/release YOK. Sürüm bump YOK.
