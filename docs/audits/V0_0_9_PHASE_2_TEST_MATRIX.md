# v0.0.9 Phase 2 — Test Matrisi

Taban: `d5bd35f` · Dal: `audit/v0.0.9-deep-review` · Tarih: 2026-08-06

**Kırmızı satırlar bilerek başarısızdır** — bunlar üretim kusurlarını yeniden
üreten adversarial testlerdir, normal suite'e dahil değildirler.

## Adversarial reproduction sonuçları

| Test | Sonuç | Üretim yoluna ulaştı | Beklenen değişmez | Gerçek durum | Blocker |
|---|---|---|---|---|---|
| `BackupAuthenticityReproduction` | **FAIL** (kasıtlı) | evet | değiştirilmiş yedek reddedilir | 874,5 → 777.777,77 kabul edildi | P0-1 |
| `RecurringIdempotency::retry` | **FAIL** (kasıtlı) | evet | aynı vade tek etki | 2 işlem, bakiye 1000→800 | P0-2 |
| `RecurringIdempotency::refund` | **FAIL** (kasıtlı) | evet | iade bir kez | 2 income, bakiye 1000→1100 | P0-3 |
| `RecurringIdempotency::corrupt_amount` | **FAIL** (kasıtlı) | evet | bozuk tutar fail-closed | işlem yazıldı, vade ilerledi | P0-2 ile birlikte |
| `CrossTransactionAtomicity::asset_sale` | **FAIL** (kasıtlı) | evet | tek atomik işlem | nakit +300, varlık silinmedi | P0-4 |
| `CrossTransactionAtomicity::debt` | **FAIL** (kasıtlı) | evet | ledger başarısızsa rollback | paid 0→1, ledger 0 işlem | P0-5 |
| `RestoreRollbackReproduction` | **FAIL** (kasıtlı) | evet | restore hatası tam rollback | config geri alınmadı | P1-1 |
| `InputBoundaryReproduction` (NaN) | **FAIL** (kasıtlı) | evet | domain sınırında ValueError | SQLite `IntegrityError` | P2-1 |
| `ExportPermissionReproduction` | **FAIL** (kasıtlı) | evet | `0600` | `0644`, plaintext | P2-4 |
| `MigrationCrashConsistency` | **FAIL** (kasıtlı) | evet | retry backfill yapar | `account_type` kalıcı `None` | P1-2 |
| `NonFiniteCorruption` **(yeni)** | **FAIL** (kasıtlı) | evet | infinity reddedilir | bakiye `-inf`→`NULL`, toplam 7500→2500 | **P0-6** |

## Property testleri (geçen)

| Test | Sonuç | Mutation doğrulaması |
|---|---|---|
| `installment_quantization_and_remainder_preserve_principal` | PASS | **doğrulandı** — quantization kaldırılınca `Decimal('0.01') != Decimal('0.00')` |
| `real_installment_schedule_sums_to_the_principal` **(yeni)** | PASS | **doğrulandı** — remainder düzeltmesi kaldırılınca 3 vakada kırıldı |
| `savings_deposit_withdraw_roundtrip` | PASS | — |
| `failed_savings_write_preserves_state` | PASS | — |
| `encrypt_decrypt_serialize_preserves_fiat_value` | PASS | — |
| `backup_restore_preserves_semantic_financial_state_hash` | PASS | — |

## Non-finite girdi matrisi (ölçülmüş)

| Girdi | Exception | İşlem | Ledger olayı | Bakiye |
|---|---|---|---|---|
| `NaN` | `IntegrityError` (SQLite) | 0 | **+0** | değişmedi |
| `inf` | **YOK** | **+1** | **+1** | **5000 → -inf** |
| `-inf` | **YOK** | **+1** | **+1** | **-inf → NULL** |
| `1e309` | **YOK** | **+1** | **+1** | **NULL** |

`balance_events` sayısı test öncesi ve sonrası ayrı ayrı ölçüldü; NaN için
delta **0**, infinity için **+1**.

## Migration normal matrisi

| Sürüm | Migration | Bakiye | İşlem | Şifreli alan | İdempotent | `user_version` |
|---|---|---|---|---|---|---|
| v0.0.1 → current | temiz | korundu | korundu | çözülebilir | evet | 0 |
| v0.0.4 → current | temiz | korundu | korundu | çözülebilir | evet | 0 |
| v0.0.6 → current | temiz | korundu | korundu | çözülebilir | evet | 0 |
| v0.0.2/3/5/7/8 | önceki turda üretildi | — | — | — | — | 0 |

## Denetlenmeyen alanlar

Aşağıdakiler **koşulmadı**. Boş sonuç geçti değildir.

| Alan | Durum |
|---|---|
| Encryption key lifecycle | Not started |
| Recovery parolası senaryoları | Not started |
| Concurrency / iki worker yarışı | Not started |
| Resource leak (RSS/thread/fd/callback) | Not started |
| Dependency güvenlik taraması | Not started |
| Backup matrisi (truncated, traversal, symlink, çift restore) | Not started |
| Migration fault injection — 15 nokta | Not started |
| 16 finansal işlemde atomicity | Not started |
| Windows runtime | Blocked by environment |
| Gerçek Tab / DPI / klavye | Blocked by environment |

---

## Final execution addendum (supersedes incomplete rows above)

| Domain / command | Result | Invariant / measured evidence | Status |
|---|---|---|---|
| `test_adversarial_reproductions -v` | 6 intentional FAIL, 0 ERROR | P0-1..P0-5 retained | Confirmed |
| `test_phase2_additional_reproductions -v` | 4 intentional FAIL, 0 ERROR | P0-6, restore config, CSV 0644, NaN boundary | Confirmed |
| `test_phase2_financial_properties -v` | 6 PASS | schedule/remainder mutations caught | Completed |
| `test_migration_fault_injection -v` | 1 intentional FAIL | ALTER persists, backfill skipped | Confirmed P1-2 |
| `test_phase2_concurrency -v` | 3 FAIL, 1 PASS | recurring 2x, refund 2x, card debt 120/limit100; savings safe | Confirmed P0-2/3/7 |
| `test_phase2_nonfinite_matrix -v` | 3 FAIL, 1 PASS | account/savings/recurring infinity corrupt; asset rejects | Confirmed P0-6 family |
| `test_phase2_backup_archive -v` | 1 PASS, 1 FAIL | POSIX traversal blocked; unexpected member accepted | P2-6 confirmed |
| `check_resource_leaks.py` | completed | FD 4→71→4 after further work/GC; thread 1 | Strong evidence P2 |
| Crypto/key/recovery group | 67 PASS, 1 skip | wrong/tampered keys, recovery/rotation fail closed | Linux completed; Windows blocked |
| `check_schema_consistency.py` | 8/8 current migration PASS | populated v0.0.1–v0.0.8, `user_version=0` | Completed |
| `pip-audit` | blocked | PyPI DNS unavailable | Blocked by environment |
| Bandit/static | completed | B413 tool false-positive candidate; no eval/exec/shell=True found | Partially completed |

### Version gate mutation result

| Mutation | Gate |
|---|---|
| installer version, workflow default, CHANGELOG heading | FAIL (caught) |
| workflow fallback, added README stale text, release asset rename, git tag mismatch | PASS (false negative) |
