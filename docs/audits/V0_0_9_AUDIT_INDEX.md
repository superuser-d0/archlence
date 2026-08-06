# v0.0.9 Denetim İndeksi

Taban: `d5bd35f` · Dal: `audit/v0.0.9-deep-review`

## Belgeler

| Dosya | İçerik |
|---|---|
| `V0_0_9_DEEP_AUDIT.md` | Phase 1 — kapı bütünlüğü, mutation testing |
| `V0_0_9_TEST_MATRIX.md` | Phase 1 test matrisi |
| `V0_0_9_RELEASE_GATE.md` | Phase 1 release gate |
| `V0_0_9_DEEP_AUDIT_PHASE_2.md` | Phase 2 — üretim davranışı, adversarial |
| `V0_0_9_PHASE_2_TEST_MATRIX.md` | Phase 2 test matrisi |
| `V0_0_9_PHASE_2_RELEASE_GATE.md` | Phase 2 release gate — **NO-GO** |

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

| Alan | Durum |
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

**Adversarial testler normal suite'e dahil değildir ve bilerek kırmızıdır.**
Düzeltmeler yapıldıkça yeşile dönmeleri beklenir.
