# v0.0.9 Denetim İndeksi

Taban: `d5bd35f` · Dal: `audit/v0.0.9-deep-review` → `fix/v0.0.9-reliability`

**GÜNCEL STATÜ tek yerde:** `V0_0_9_PRE_WINDOWS_GATE.md`. Bu indeksteki
Phase 1/2 tabloları o fazların KENDİ anlarını kaydeder; sonradan kapanan
maddeler için o tabloları değil, aşağıdaki Phase 3 belgelerini okuyun.

## Belgeler

| Dosya | İçerik |
|---|---|
| `V0_0_9_DEEP_AUDIT.md` | Phase 1 — kapı bütünlüğü, mutation testing |
| `V0_0_9_TEST_MATRIX.md` | Phase 1 test matrisi |
| `V0_0_9_RELEASE_GATE.md` | Phase 1 release gate |
| `V0_0_9_DEEP_AUDIT_PHASE_2.md` | Phase 2 — üretim davranışı, adversarial |
| `V0_0_9_PHASE_2_TEST_MATRIX.md` | Phase 2 test matrisi |
| `V0_0_9_PHASE_2_RELEASE_GATE.md` | Phase 2 release gate — **NO-GO** (o an) |
| `V0_0_9_PHASE_3_BASELINE.md` | Phase 3 başlangıç durumu |
| `V0_0_9_PHASE_3_FIX_REPORT.md` | Phase 3 düzeltme raporu — **anlık görüntü** (`6bb7a4f`) |
| `V0_0_9_PHASE_3_TEST_MATRIX.md` | Phase 3 test matrisi — **anlık görüntü** (`493dd3c`) |
| `V0_0_9_PHASE_3_HANDOFF.md` | Phase 3 devir notu |
| `V0_0_9_PHASE_3_CONTINUATION.md` | Phase 3 kapanış durumu + **tam commit zinciri** |
| `V0_0_9_PHASE_3_RELEASE_GATE.md` | Phase 3 release gate — RC GO, pending Windows |
| `V0_0_9_PRE_WINDOWS_GATE.md` | **Windows öncesi son kapı — GÜNCEL STATÜ.** P2-7 yeniden değerlendirmesi, FD ölçüm matrisi, açık iş listesi |

## Phase 1 — kapılar yalan söylüyor mu

**Yöntem:** mutation testing. 14 mutation, 13 yakalandı, 1 kaçtı.

| Alan | Durum |
|---|---|
| Test-gate bütünlüğü | Completed |
| Mutation sonuçları | Completed |
| İstisna kapısı | Completed — A-1, A-2 |
| İlk migration incelemesi | Completed |

Bulgular: **A-1** kapı bypass'ı (P1) · **A-2** baseline slack'i (P1) ·
**A-3** taksit quantization koruması (P2, **Phase 2'de kapandı**) ·
**A-4** FK zorlanmıyor (P2) · **A-5** `user_version` yok (P3) ·
**A-6** CHANGELOG eksik (P3).

## Phase 2 — uygulama yanlış durum üretiyor mu

**Yöntem:** üretim yoluna ulaşan adversarial testler + fault injection +
property-based testing.

> Aşağıdaki tablo **Phase 2'nin kendi anını** kaydeder. `Not started` /
> `Partially completed` satırlarının çoğu Phase 3'te kapandı — güncel
> statü için `V0_0_9_PHASE_3_CONTINUATION.md` ve
> `V0_0_9_PRE_WINDOWS_GATE.md`. Özellikle *Resource leak* satırı:
> o turda **P2-7** olarak açılan bulgu, `V0_0_9_PRE_WINDOWS_GATE.md` §3'te
> denetim probe'unun kendi sızıntısı olduğu kanıtlanarak kapandı.

| Alan | Durum (Phase 2 anı) |
|---|---|
| Backup authenticity | Completed — P0-1 |
| Backup/restore completeness | Partially completed — P1-1 |
| Backup/restore failure recovery | Partially completed |
| Encryption key lifecycle | Not started |
| Recovery senaryoları | Not started |
| Recurring charge idempotency | Completed — P0-2 |
| Recurring refund idempotency | Completed — P0-3 |
| Asset atomicity | Completed — P0-4 |
| Debt atomicity | Completed — P0-5 |
| Diğer finansal atomicity | Not started |
| Concurrency | Not started |
| Financial property testing | Completed |
| Migration normal matrix | Completed |
| Migration fault injection | Partially completed — P1-2 |
| Input validation | Completed — **P0-6**, P2-1 |
| UI / localization | Partially completed |
| Performance scaling | Completed |
| Resource leak | Not started |
| Linux packaging | Partially completed |
| Windows packaging | Blocked by environment |
| Upgrade workflow | Partially completed — P2-3 |
| Dependency / security | Not started |
| Observability | Partially completed |
| Version / release consistency | Partially completed — P2-2 |
| RC / soak readiness | Not started |

## Birleşik blocker listesi

**P0:** P0-1 backup authenticity · P0-2 charge idempotency ·
P0-3 refund idempotency · P0-4 asset atomicity · P0-5 debt atomicity ·
P0-6 infinity corruption

**P1:** P1-1 restore rollback · P1-2 migration backfill ·
P1-3 kapı bypass'ı · P1-4 kapı slack'i

## Denetim araçları

| Dosya | Amaç |
|---|---|
| `scripts/audit/check_financial_invariants.py` | Salt okunur değişmez taraması |
| `scripts/audit/check_schema_consistency.py` | Şema/migration matrisi |
| `scripts/audit/test_adversarial_reproductions.py` | P0-1..P0-5 |
| `scripts/audit/test_phase2_additional_reproductions.py` | P0-6, P1-1, P2-1, P2-4 |
| `scripts/audit/test_phase2_financial_properties.py` | Property testleri |
| `scripts/audit/test_migration_fault_injection.py` | P1-2 |

| `scripts/audit/test_phase2_concurrency.py` | deterministic two-worker P0-2/P0-3/P0-7 evidence |
| `scripts/audit/test_phase2_nonfinite_matrix.py` | multi-service P0-6 evidence |
| `scripts/audit/test_phase2_backup_archive.py` | traversal/allow-list evidence |
| `scripts/audit/check_resource_leaks.py` | temporary-profile backend resource trend (probe'un kendi sızıntısı `28e43f0`'da düzeltildi — bkz. `V0_0_9_PRE_WINDOWS_GATE.md` §3) |
| `scripts/audit/version_mutation_matrix.py` | 16 vakalık sürüm tutarlılık mutation matrisi |
| `tests/test_connection_ownership_contract.py` | Bağlantı sahipliği — açma/kapama sayımı, platformdan bağımsız |

## Final Phase 2 status

**Completed with environment limitations.** The final 25-row ledger is in
`V0_0_9_DEEP_AUDIT_PHASE_2.md` section 8; it contains no `Not started` row.
The Phase 3-only confirmed/strong-evidence handoff is
`V0_0_9_PHASE_3_HANDOFF.md`.

**Adversarial testler normal suite'e dahil değildir ve bilerek kırmızıdır.**
Düzeltmeler yapıldıkça yeşile dönmeleri beklenir.
