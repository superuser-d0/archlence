# Devir Raporu — Claude → Codex

**Tarih:** 2026-08-06 · **Depo:** `superuser-d0/archlence` · **main:** `9172cd4`

Bu dosya bir sonraki oturum için bağlamdır. Okuduktan sonra silinebilir.

---

## 0. EN ÖNEMLİ MADDE — ROADMAP GÜNCELLENMELİ

`docs/ROADMAP.md`'nin **`main` üzerindeki hâli bayat.** Faz 1 madde 5'in
kapanış notu hâlâ şunu iddia ediyor:

> `decrypt()`'s fail-open behavior ... is unchanged for both formats — flipping
> that touches the same ~55 call chains ... unsafe to change blind without a way
> to verify GUI behavior here.

**Bu iki noktada da yanlış** ve düzeltmesi **PR #59'un içinde, henüz merge
edilmedi:**

- `decrypt()` PR #22'den beri zaten tipli istisna fırlatıyor. Bayat olan
  **çağıranlardı**.
- 55 değil **21** çağrı yeri var, ve düzeltme mekanik + unit-testable.

**Codex'ten istenen:** PR #59 merge edildikten sonra ROADMAP'in bu maddesinin
gerçekten güncellendiğini doğrula (PR #59 zaten bir commit ile güncelliyor —
`docs: correct the stale "decrypt() is still fail-open" entry`). PR #59 merge
edilmeden başka bir dal açıp ROADMAP'e dokunulursa çakışma çıkar.

**Neden bu kadar önemli:** bu oturumda ROADMAP'te **üç ayrı bayat madde**
bulundu. Her seferinde "yapılmamış" denen iş aslında yapılmıştı ve doğrulamak
saatler aldı. Bayat roadmap, bir sonraki oturumu yanlış yöne sürüyor.

| Madde | ROADMAP ne diyordu | Gerçek |
|---|---|---|
| Faz 1 · 3 (exe smoke test) | "yapılmadı" | Üç smoke test zaten vardı; gerçek boşluk `crash.log` kontrolünün 3'ten 1'inde olmasıydı |
| Faz 1 · 5 (OS keystore) | "adaptör açık" | DPAPI + Secret Service/KWallet yazılmıştı |
| Faz 1 · 5 (migration) | "başlanmadı" | Yazılmış, UI'a bağlanmış; gerçek boşluk test kapsamıydı |

---

## 1. Şu anki durum

**Yayında:** v0.0.5 pre-release (4 Ağustos). `main` = `9172cd4`.

**Açık PR'lar — ikisi de YEŞİL, merge bekliyor:**

| PR | Dal | İçerik |
|---|---|---|
| [#59](https://github.com/superuser-d0/archlence/pull/59) | `fix/decrypt-error-contract` | `decrypt()` çağıran 21 nokta + 3 gerçek hata + ROADMAP düzeltmesi |
| [#60](https://github.com/superuser-d0/archlence/pull/60) | `fix/account-dialog-and-tab-focus` | Hesap diyaloğu UX (3 hata) + sıfırlama (2 hata) + dashboard önbelleği |
| [#53](https://github.com/superuser-d0/archlence/pull/53) | `packaging/arch-logo` | Bu oturumdan DEĞİL, önceden açık |

**Sıra önemli değil** — #59 ve #60 bağımsız, çakışmıyor.

### `main` üzerinde ölçülen güncel sayılar

```
geniş/bare exception handler : 143   (CI kapısı korunuyor)
pyflakes bulgusu             : 116   (107 F841 + 9 F401, bloklamıyor)
test                         : 650   (PR'larla 656+)
```

---

## 2. GPT'nin eleştirilerine karşılık — hangisi çözüldü

GPT değerlendirmesini **GitHub'daki `main`'e bakarak** yaptı, yani açık iki
PR'daki işi göremedi. Aşağıda ayrım net tutuldu.

### ✅ Zaten `main`'de çözülmüş (GPT de doğru tespit etmiş)

| Eleştiri | Durum |
|---|---|
| `v1.x stable` etiketi olgunluğu abartıyor | 0.0.x pre-release hattına geçildi |
| Tutar alanı yanlış rakam kaydediyor | Düzeltildi, regresyon testi var |
| Varlık alımı yanlış hesaptan düşüyor | Düzeltildi + "zaten sahibim" seçeneği (v0.0.5) |
| UI ana thread'de ağır iş | Takvim/bütçe/kategori birleştirildi, abonelik RecycleView |
| Windows yeterince test edilmiyor | Test paketi Windows'ta koşuyor + kurulum/açılış/yükseltme/kaldırma smoke |
| `print()` hataları gizliyor | 108/109 dosya günlüğüne taşındı |
| Tek fiyat sağlayıcı | CoinGecko + Frankfurter fallback (v0.0.5) — kripto/döviz için |

### 🟡 Açık PR'da çözüldü — GPT bunları göremedi

| Eleştiri | Nerede |
|---|---|
| **PR #59 en kritik mesele** | PR #59'un **kendisi tamamlandı ve yeşil.** GPT'nin gördüğünden fazlasını da içeriyor: `export_all_to_csv` bağlantı sızıntısı, `get_asset_transaction_history` hata işleyicisinin `IndexError` ile çökmesi, ve **toplam besleyen yolların** (grafik + bütçe rezervi) artık `0.0`'a düşmek yerine `FinancialDataIntegrityError` fırlatması |
| Kivy UI kasması | PR #60: dashboard metrik önbelleği — 10.000 işlemde **328 ms → 0 ms** (tekrar tazelemede). Profillendi: maliyetin %99'u AES-GCM çözme |
| Sıfırlama sonrası tutarsız ekran | PR #60: "verileri sil" sonrası algoritmik öngörü ve varlık geçmişi de temizleniyor |
| UX'te yanlış kayıt riski | PR #60: TAB alanlar arası geçiyor (metne sekme yazmıyordu), kart numarası opsiyonel olduğu **yazıyor** |

### ❌ Hâlâ açık — GPT haklı, dokunulmadı

| Eleştiri | Not |
|---|---|
| **Decimal geçişi tamamlanmamış** | README'de bilinen kısıt olarak duruyor. **Bu oturumda hiç ele alınmadı.** Muhtemelen en yüksek değerli sıradaki iş. |
| **143 geniş exception hâlâ yüksek** | Sayı doğru. Kalanların çoğu bilinçli sınır (işaretli), ama mimari bağlılık işareti olarak GPT haklı. |
| **116 pyflakes bulgusu** | 107 `F841` + 9 `F401`. Toplu temizlik, bloklamıyor. |
| **Gerçek Windows donanımında DPAPI doğrulaması** | Kod yazılmış, Linux tarafı ölçülmüş; Windows yolu hiç çalıştırılmadı. |
| **Recovery/keystore senaryoları** | Veriler ve Gizlilik'teki 8 akışın gerçek tıklama testleri yok (pencere gerekiyor). |
| **Bağımsız inceleme yok** | Ledger, migration, backup/restore ve anahtar yönetimi için dışarıdan teknik inceleme hâlâ yapılmadı. |
| **Kapsam çok geniş / özellik dondurma** | Ürün kararı. Bu oturumda yeni özellik eklenmedi (sadece hata düzeltme + test), yani doğru yönde. |
| **Kod imzalama sertifikası** | Yok. Windows SmartScreen uyarısının sebebi. |

### ⚠️ GPT'nin bilmediği, yol boyunca bulunan ek borç

- **20 fonksiyonda korumasız `conn.close()`** (`try/finally` yok). Hiçbiri şu
  anki değişikliklerden erişilebilir değil (decrypt içerenlerde bağlantı
  çözmeden önce kapanıyor — fonksiyon fonksiyon doğrulandı), ama gerçek borç.
- **`build-windows.yml`'de üç adet `Start-Process ... -Wait`** — süresiz
  bekliyor. Bu oturumda bir runner takıldı ve adım job'ın 30 dakikalık
  sınırına kadar oturdu (23 dakika). `WaitForExit(ms)` ile hızlı başarısızlığa
  çevrilebilir.
- **`asset_mixin::_fetch_and_enrich`** içinde `enrich_assets_from_cache` ve
  `fetch_asset_prices_async` korumasız — hata alırlarsa thread ölür ve
  "Varlıklar hazırlanıyor…" iskeleti kalıcı olarak ekranda kalır.

---

## 3. Bu oturumda öğrenilen — tekrar keşfetmeyin

### Windows, Linux'un göremediğini yakalıyor

Bu oturumda **üç ayrı hata** yalnızca `test-windows`'ta göründü. Üçü de aynı
kök nedene dayanıyor: **Linux açık bir dosyanın silinmesine izin veriyor,
Windows vermiyor.** Yerelde 656 test yeşilken hiçbiri görünmüyordu.

1. `with sqlite3.connect(...)` bağlantıyı **kapatmaz** (yalnızca işlemi
   yönetir) → `contextlib.closing` kullanın
2. `export_all_to_csv` `try/finally` olmadan `conn.close()` → **üretim kodu
   hatasıydı**, `managed_connection`'a taşındı
3. Testte `delete_all_data`'nın açtığı daemon thread'ler `tearDown` ile
   yarışıyordu → mock'layın ya da `join` edin

### Test yazarken düşülen tuzaklar

- **`@skipUnless(...)` IMPORT anında çalışır.** İçinde `kivy.core.window`
  import etmek, test toplama aşamasında Kivy'nin metrik başlatmasını tetikleyip
  **125 ilgisiz testi** kırdı. Kontrolü `setUpClass` içine alın.
- **`_t(...)` üzerinden assert etmeyin.** Türkçe modda `tr()` anahtarı olduğu
  gibi döndürür; sözlükte ne yazarsa yazsın assert geçer. Test dişsiz olur.
- **Headless pakette KivyMD widget'ı kurulamaz** (`MDApp` çalışan bir `Window`
  ister). Saf mantık için stub kullanın.
- **Karşılaştırmalı ölçümde, düzeltmeyle gelen bir işarete göre saymayın.**
  Eski kodda o işaret yoktur, sayaç hep 0 verir ve "hata yok" gibi görünür.

### Ölçüm disiplini

Bu oturumda **kendi ölçümüm iki kez geçersizdi** ve düzeltildi:

- Sızıntı probe'u istisnayı hemen yutuyordu → frame ölüyor, refcount bağlantıyı
  kapatıyor, "sızıntı yok" çıkıyordu. **Traceback'i canlı tutunca** gerçek fark
  göründü (2 → 1).
- "Korumasız `conn.close()` başka yok" iddiası yanlıştı: heuristik fonksiyonda
  herhangi bir `try` var mı diye bakıyordu, oysa soru `close()`'un korunup
  korunmadığıydı. Sıkı kontrolle 20 tane çıktı.

**Kural:** her daraltma/önbellek için "dişini" kanıtlayın — davranışı geri alıp
testin gerçekten kırıldığını görün. Bu oturumda bir test bu kontrolde dişsiz
çıktı ve yeniden yazıldı.

---

## 4. Önerilen sıra

1. **PR #59 ve #60'ı merge et** (ikisi de yeşil, bağımsız)
2. **Decimal geçişi** — GPT'nin haklı olduğu en büyük açık madde, README'de
   zaten bilinen kısıt olarak duruyor
3. `build-windows.yml`'deki `Start-Process -Wait` zaman aşımı
4. `asset_mixin::_fetch_and_enrich` garantili tamamlanma sınırı
5. 20 korumasız `conn.close()`
6. 116 pyflakes toplu temizliği
7. Gerçek Windows'ta DPAPI + Veriler/Gizlilik tıklama akışları

**Yeni özellik eklenmemeli.** GPT'nin bu tavsiyesi doğru ve bu oturumda zaten
uygulandı: tamamı hata düzeltme, test ve doğrulama.

---

## 5. Doğrulama komutları

```bash
KIVY_NO_ARGS=1 ARCHLENCE_HEADLESS=1 python run_tests.py
python -m flake8 . --select=F821,F822,F823,E722 --exclude=.venv,venv,build,dist,.git,AppDir,pkg,src --count
python scripts/audit_exception_handlers.py --check .github/exception-baseline.json
python scripts/check_version_consistency.py
```

`AppDir`, `pkg`, `src` hariç tutulmalı: yerel `makepkg` çıktısı KivyMD'nin
kendi kaynağının kopyasını taşıyor ve tarayıcıları yanıltıyor (bu oturumda
iki yanlış pozitife sebep oldu, ikisi de düzeltildi).
