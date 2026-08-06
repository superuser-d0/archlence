# v0.0.9 Phase 3 — Düzeltme Raporu

> **BU BELGE BİR ANLIK GÖRÜNTÜDÜR — `6bb7a4f` HEAD'inde yazıldı.**
> Aşağıdaki "Açık işler" ve "RC kararı: NO-GO" satırları O AN doğruydu;
> **bugünün statüsü değildir.** Güncel durum:
> `V0_0_9_PHASE_3_CONTINUATION.md` ve `V0_0_9_PRE_WINDOWS_GATE.md`.
> Kayıt olduğu gibi bırakıldı — denetim izinin bir parçası.

**Dal:** `fix/v0.0.9-reliability` · **HEAD:** `6bb7a4f` · **Taban:** `d5bd35f`
**Status (o an): Phase 3 fixes in progress, RC blocked**

---

## Statü düzeltmesi

Önceki ara rapor **P1-1'i "Closed" yazarken** aynı belgede
`recover_interrupted_restore()`in hiçbir üretim yolundan çağrılmadığını da
belirtiyordu. İkisi birlikte doğru olamaz.

Bu tur o boşluğu kapattı (`616224f`) ve statü aşağıda alt bileşen düzeyinde
verilmiştir.

---

## P0 kapanış tablosu

| ID | Status | Kanıt | Commit |
|---|---|---|---|
| P0-1 backup authenticity | **Closed** | koordineli DB+hash tamper reddediliyor | `0368853` |
| P0-2 charge idempotency | **Closed** | sequential + concurrent tek etki | `b9e5736` |
| P0-3 refund idempotency | **Closed** | ikinci iade reddediliyor | `b9e5736` |
| P0-4 asset atomicity | **Closed** | 4 fault noktası, tam rollback | `96049ee`, `bfb2b37` |
| P0-5 debt atomicity | **Closed** | 3 fault noktası, tam rollback | `df46a31`, `bfb2b37` |
| P0-6 non-finite | **Closed** | nonfinite matrisi, write öncesi ret | `998584e` |
| P0-7 kart limiti TOCTOU | **Closed** | concurrency testi | `467b269` |

---

## P1-1 — Restore generation atomicity

**Status: Closed — visual/manual presentation validation pending**

| Alt bileşen | Status | Kanıt |
|---|---|---|
| Normal exception'da DB/key/config rollback | **Closed** | 5 fault noktası, `05da34a` |
| Dayanıklı restore journal | **Closed** | `.archlence-restore/`, atomik yazım |
| Journal corruption fail-closed | **Closed** (test edildiği ölçüde) | bozuk + tanınmayan state |
| Process crash sonrası startup recovery | **Closed** | `616224f`, çağrı sırası testi |
| Recovery başarısızlığının kullanıcıya gösterimi | **Closed** (orchestration) | presenter sözleşmesi + sızıntı testi, `6bb7a4f` |
| Recovery bitmeden DB/key/config kullanımının engellenmesi | **Closed** | çağrı sırası + fail-closed testleri |
| COMMITTED marker sonrası cleanup crash | **Closed** | 6 test + 4 mutation, `efadc1c` |
| Gerçek görsel dialog rendering | **Blocked by environment** | dummy window provider; Windows/manuel listede |

**Neden "visual validation pending":** finansal kurtarma mekanizmasının tamamı
kapandı ve mutation ile doğrulandı. Kalan tek şey gerçek widget rendering'in
gözle görülmesi; bu bir finansal blocker değil, ortam sınırı.

**Root cause:** config rollback yolu yoktu; rollback generation
`TemporaryDirectory` içindeydi.
**Production fix:** `services/backup_service.py`, `services/startup_recovery.py`,
`main.py::build`.
**Failing test before:** `restore_config_rollback` →
`config_after={"profile":"from-backup"}`.
**Passing test after:** `config_after={"profile":"current"}`.
**Mutation:** config rollback kaldır → 3 assertion; journal'ı geçici dizine al
→ kurtarma testleri; startup çağrısını kaldır/taşı/yut → 3 mutation.
**Normal-suite test:** `tests/test_restore_generation_atomicity.py` (7),
`tests/test_startup_recovery_integration.py` (8).
**Remaining limitation:** COMMITTED-cleanup senaryosu; gerçek UI gösterimi.
**Windows manual verification:** yapılmadı.

---

## P1-2 — Migration crash recovery

**Status: Closed**

**Root cause:** backfill `if column not in cols` bloğunun içindeydi; `ALTER`
kalıcı olunca sonraki açılış bloğa hiç girmiyordu.
**Production fix:** `database/init_db.py` — şema adımı ile veri adımı ayrıldı,
backfill kendi postcondition'ına bakıyor.
**Failing test before:** `account_type_after_retry=None`.
**Passing test after:** `account_type_after_retry='credit_card'`.
**Mutation:** backfill'i ALTER bloğuna geri al → 2 test kırıldı.
**Normal-suite test:** `tests/test_migration_retry_safety.py` (4).
**Migration matrix:** v0.0.1–v0.0.8 `state/fresh_schema/idempotent` hepsi True.
**Remaining limitation:** `user_version` hâlâ 0 (A-5, P3).
**Commit:** `652d512`

---

## A-1 / A-2 — Exception quality gate

**Status: Closed**

**Root cause:** tespit yalnızca `ast.Name` tanıyordu; karşılaştırma yalnızca
`current - baseline` (fazlalık) bakıyordu.
**Production fix:** `scripts/audit_exception_handlers.py` — `_is_broad()`,
`_broad_aliases()`, `_normalized_expression()`, tam eşitlik.
**Failing before:** 4 bypass sondası → "144 handler korundu", exit 0.
**Passing after:** "Yeni geniş handler=4", exit 1.
**Slack:** handler daraltma → "kaybolan (baseline slack)=1" + yönerge, exit 1.
**Normal-suite test:** `tests/test_exception_gate.py` (19).
**Commit:** `6877dd5`

---

## Test güvenilirliği düzeltmesi

**Status: Closed** · **Commit:** `493dd3c`

Fault reproduction'ları yalnızca son duruma bakıyordu. Enjeksiyon noktası
koddan kaybolursa fault hiç tetiklenmiyor, test yanlış sebeple sonuç
veriyordu. Artık hook'un çağrıldığı ayrıca doğrulanıyor.

**Kayıt:** normal suite `bfb2b37` öncesinde 3 HATA ile kırmızıydı
(`tests/test_asset_sale_cash_amount.py`, `KeyError: 'amount'`). Hatayı ekleyen
commit `96049ee`. Testlerin neden sonucu görülmeden commit edildiği hakkında
**kanıt yok**; yalnızca durum kaydedildi.

---

## Açık işler

Sağdaki sütun bu belgenin yazılmasından SONRA ne olduğunu gösterir; sol
taraf `6bb7a4f` anındaki kaydın kendisidir.

| # | İş | Status (`6bb7a4f`) | Sonradan |
|---|---|---|---|
| 3 | Deterministic connection cleanup | **Open** | Kapandı — bulgu yanlış atıfmış (`28e43f0`); ayrı üretim eksiği `dac9a15` |
| 4 | Version consistency mutation matrisi (16 vaka) | **Open** | Kapandı — `5d05084` + `1223935`, 16/16 |
| 5 | Packaging/upgrade gate (`0.0.1` fallback, sabit upgrade kaynağı) | **Open** | Kapandı — `ddda5ed` (runtime doğrulaması Windows'ta) |
| 6 | **P2-6** asset açıklama regresyonu | **Open** | Kapandı — `8b1744e` |
| 7 | Kalan testlerin CI'a taşınması | **Partially** | Job kapandı (`ad6296f`); ZORUNLU olması hâlâ açık — branch protection, bkz. `V0_0_9_PRE_WINDOWS_GATE.md` §8 |
| 8 | CHANGELOG + dokümantasyon | **Partially** | Kapandı — `3cdff27`, `2bd5f0d`, `3551049` ve bu tur |
| — | COMMITTED-cleanup crash senaryosu | **Open** | Kapandı — `efadc1c`; gerçek process-kill doğrulaması Windows'ta |
| — | Gerçek Windows doğrulaması | **Blocked by environment** | Hâlâ blocked — sıradaki tur |

---

## Doğrulama

```
normal suite      741 test OK (skip 2)   ← tur başında 733
bloklayan lint    0
istisna kapısı    145 handler yeşil
sürüm kapısı      0.0.8 / tag v0.0.8
adversarial       10/10 PASS
migration matrisi v0.0.1–v0.0.8 yeşil
git diff --check  temiz
```

## RC kararı: **NO-GO**

Push/PR/tag/release YOK. Sürüm bump YOK.
