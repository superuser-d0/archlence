# v0.0.9 Phase 3 — Release Gate

HEAD: `2bd5f0d` · Taban: `d5bd35f` · 32 commit
Tam commit zinciri: `V0_0_9_PHASE_3_CONTINUATION.md` → "Commit zinciri"

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
| Connection cleanup | **Closed** | yeniden ölçüldü, delta 0; davranış testle sabitlendi |
| Version mutation matrisi | **Closed** | 16/16 yakalandı |
| Packaging/upgrade gate | **Closed** | fallback kaldırıldı, taban semver ile seçiliyor |
| P2-6 asset açıklama | **Closed** | miktar/fiyat/K-Z geri geldi |

## RC GO için kalan somut koşullar

- [x] Connection cleanup bounded, explicit GC'ye bağlı değil
- [x] 16 version mutation vakasının tamamı yakalanıyor
- [x] Windows workflow `0.0.1` fallback'inden kurtuldu
- [x] Upgrade smoke gerçek önceki sürümü seçiyor
- [x] P2-6 kapandı
- [x] Kalan reliability testleri zorunlu CI kapsamında (`reliability-gates`)
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
