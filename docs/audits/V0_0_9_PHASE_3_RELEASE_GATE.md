# v0.0.9 Phase 3 — Release Gate

HEAD: `493dd3c`

## Karar: **RC NO-GO**

Bütün P0'lar Closed. **P1-1 Partially closed**, ve RC GO koşullarından beşi
açık.

## Blocker tablosu

| ID | Status | Neden hâlâ blocker |
|---|---|---|
| P0-1 … P0-7 | **Closed** | — |
| P1-1 restore generation | **Partially closed** | COMMITTED-cleanup crash senaryosu test edilmedi; UI gösterimi doğrulanmadı |
| P1-2 migration retry | **Closed** | — |
| A-1 / A-2 kapı | **Closed** | — |
| Connection cleanup | **Open** | FD 4→71 davranışı yeniden ölçülmedi |
| Version mutation matrisi | **Open** | 16 vakanın hiçbiri koşulmadı |
| Packaging/upgrade gate | **Open** | `0.0.1` fallback ve sabit `v0.0.1` upgrade kaynağı duruyor |
| P2-6 asset açıklama | **Open** | ledger açıklaması miktar/fiyat/K-Z kaybetti |

## RC GO için kalan somut koşullar

- [ ] COMMITTED-cleanup crash senaryosu test edildi
- [ ] Connection cleanup bounded, explicit GC'ye bağlı değil
- [ ] 16 version mutation vakasının tamamı yakalanıyor
- [ ] Windows workflow `0.0.1` fallback'inden kurtuldu
- [ ] Upgrade smoke gerçek önceki sürümü seçiyor
- [ ] P2-6 kapandı veya gerekçeli ertelendi
- [ ] Kalan reliability testleri zorunlu CI kapsamında
- [ ] CHANGELOG `## Unreleased` güncel
- [ ] Gerçek Windows checklist hazır

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
