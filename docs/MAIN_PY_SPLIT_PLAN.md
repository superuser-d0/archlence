# `main.py` ayrıştırma planı

**Durum: AYRIŞTIRMA ONAY BEKLİYOR.** §3'teki altı dilimin hiçbiri
yapılmadı; `main.py` ve controller'lar konusunda kod değişmedi.

**İstisna — §4'teki önkoşul yapıldı:** `tests/test_kv_app_surface.py` yazıldı
ve merge edildi. Bu, ayrıştırmanın onaylandığı anlamına GELMEZ; o kapı
ayrıştırma hiç yapılmasa bile değerli olduğu için ayrıca ele alındı.

Kaynak madde: [`docs/ROADMAP.md`](ROADMAP.md) — açık iş 1. Ekran davranışı
ayrı controller/view-model sınıflarına ayrılacak, `ArchlenceApp` yalnız
uygulama yaşam döngüsüne inecek.

---

## 0. Ölçülen mevcut durum

2026-08-17 itibarıyla ölçülen değerler:

| | Ölçülen |
|---|---|
| `main.py` | **2.280 satır** |
| Mixin sayısı | **17** |
| `ui/dashboard.kv` | 2.762 satır |
| Test paketi | 996 test |

Mixin'lerin dağılımı — asıl kütle `main.py`'de değil, mixin'lerde:

| Mixin | Satır | Metot | Test dosyası |
|---|---|---|---|
| `asset_mixin` | 2032 | 69 | 6 |
| `transaction_mixin` | 1238 | 43 | 8 |
| `account_mixin` | 1113 | 32 | 8 |
| `budget_mixin` | 1109 | 46 | 8 |
| `calculator_mixin` | 762 | 18 | 4 |
| `insights_mixin` | 668 | 23 | 6 |
| `migration_mixin` | 630 | 36 | 2 |
| `savings_mixin` | 458 | 21 | **0** |
| `debt_mixin` | 443 | 20 | 2 |
| `calendar_mixin` | 404 | 12 | 4 |
| `subscription_mixin` | 391 | 20 | 2 |
| `history_mixin` | 381 | 15 | 2 |
| `pending_mixin` | 330 | 15 | 2 |
| `recurring_mixin` | 318 | 10 | 6 |
| `notification_mixin` | 187 | 7 | 2 |
| `scenario_mixin` | 172 | 4 | 2 |
| `search_mixin` | 160 | 7 | 0 (servisi 1) |

`main.py`'nin kendi bölümleri — zaten adlandırılmış dikişler:

| Bölüm | Satır aralığı | ~Boyut |
|---|---|---|
| Properties & State | 415-433 | 19 |
| Lifecycle & Initialization | 434-666 | 233 |
| Theming & Visuals | 667-855 | 189 |
| System Maintenance & Helpers | 856-903 | 48 |
| Metrics & Dashboard Updates | 904-1332 | 429 |
| Charting & Calculations | 1333-1369 | 37 |
| List & Navigation Interactions | 1370-1633 | 264 |
| Authentication & Profile | 1634-1862 | 229 |
| Categories & AI Insights | 1863-2109 | 247 |
| Dialogs & Reset Functionality | 2110-2272 | 163 |

**Not:** bu oturumda `SearchMixin` ve `NotificationMixin` eklendi, yani liste
15'ten 17'ye çıktı. Maddeyi bir miktar kötüleştiren değişiklik bu plandan önce
yapıldı ve kayda geçiyor.

---

## 1. Asıl kısıt: `.kv` `app`'e tek nesne olarak bağlı

Planın tamamını belirleyen şey bu, dosya boyutları değil.

- `.kv` dosyaları **33 farklı `app.<metot>()`** çağırıyor.
- `app.` toplam **344 yerde** geçiyor (`dashboard.kv` 334, `tools.kv` 10).
  Bunların 143'ü `app.tr(...)` — çeviri yardımcısı.
- `.kv` ayrıca app **property'lerine** bağlanıyor: `app.language`,
  `app.active_category_type`, `app.home_circle_color`,
  `app.key_protection_text`, `app.theme_cls...`

**Kritik olan:** Kivy `.kv` içindeki `app.foo` ifadesini ÇALIŞMA ZAMANINDA
çözer. `foo` yoksa derleme hatası olmaz — düğme sessizce hiçbir şey yapmaz.
Bu, tam olarak bu turda iki kez karşılaştığımız kusur sınıfı (arama çubuğu ve
zil: ikisi de "duruyor ama hiçbir şey yapmıyor"). 344 çağrı yerini elle
taşımak, o kusuru 344 kez üretme riski demektir.

### Bu yüzden strateji A seçiliyor

| | A — Delegasyon cephesi | B — `.kv`'yi controller'a yönlendir |
|---|---|---|
| `.kv` değişikliği | **Yok** | 344 site |
| `ArchlenceApp`'te kalan | 33+ ince delege metodu | Yalnız yaşam döngüsü |
| Hata modu | Python tarafı; testler yakalar | Sessiz çalışma zamanı arızası |
| Son hâlin temizliği | Orta | Yüksek |

**A ile başlanacak.** B, bir controller'ın dikişi kanıtlandıktan sonra
controller başına ayrı bir iş olarak ele alınabilir — ama zorunlu değil ve bu
planın kapsamında değil. Delege metotları "kirlilik" değil, `.kv`'nin genel
API'si; tek satırlık ve okunması kolay olacaklar.

---

## 2. Hedef yapı

```
main.py                     -> yalnız: crash raporlama, tek örnek kilidi,
                               Kivy kurulumu, ArchlenceApp yaşam döngüsü
                               (build/on_start/on_stop), property tanımları,
                               ve .kv'nin çağırdığı ince delege metotları

controllers/
  dashboard_controller.py   <- Metrics & Dashboard Updates (429)
                               + Charting & Calculations (37)
  navigation_controller.py  <- List & Navigation Interactions (264)
  auth_controller.py        <- Authentication & Profile (229)
  category_controller.py    <- Categories & AI Insights (247)
  theme_controller.py       <- Theming & Visuals (189)
  maintenance_controller.py <- System Maintenance & Helpers (48)
                               + Dialogs & Reset (163)
```

Mixin'ler **bu planda taşınmıyor.** Gerekçesi §5'te.

Her controller:
- `__init__(self, app)` ile app referansı alır; `self.app.root.ids...` üzerinden
  widget'lara erişir. Mevcut `self.root.ids...` kalıbının birebir karşılığı.
- Kendi durumunu tutmaz. Durum `ArchlenceApp`'in property'lerinde kalır —
  `.kv` onlara bağlı ve `StringProperty`/`ColorProperty` reaktifliği oradan
  geliyor. Durumu taşımak, `.kv` bağlarını kırar.

---

## 3. Dilimler

Her dilim **ayrı PR**. Her PR'da: tüm test paketi + dört görsel kapı + tam pyflakes +
mypy yeşil olmalı, ve uygulama gerçekten açılıp ilgili ekran görülmeli.

Sıra **kasıtlı**: en iyi test korumasına sahip ve en az bağlı bölüm önce,
böylece deseni riski düşük bir yerde kanıtlarız.

| # | Dilim | ~Satır | Neden bu sırada |
|---|---|---|---|
| 0 | Altyapı: `controllers/` paketi + `theme_controller` | 189 | Tema en yalıtık: `.kv`'den 2 çağrı (`toggle_theme`, `apply_theme`), görsel kapılar zaten koruyor. Desen burada kanıtlanır. |
| 1 | `maintenance_controller` | 211 | Küçük, arayüzle az bağlı, `confirm_delete_all_data` gibi net sınırlar. |
| 2 | `auth_controller` | 229 | Test koruması güçlü (`test_pin_lazy_migration`, `test_reset_flow`), sınırları net. |
| 3 | `category_controller` | 247 | `load_categories` `.kv`'den 3 kez çağrılıyor; ayarlar ekranı ölçülebilir. |
| 4 | `navigation_controller` | 264 | Sekme girişleri (`on_accounts_tab_enter`, `on_assets_tab_enter`) — kaydırma kapısı burayı koruyor. |
| 5 | `dashboard_controller` | 466 | **En büyük ve en riskli.** En sona bırakılıyor: o noktada desen dört kez kanıtlanmış olur. |

Dilim 5'ten sonra `main.py` beklenen boyut: **~600-700 satır** (importlar, crash
raporlama, kilit, yaşam döngüsü, property'ler, delege metotları).

### Her dilimin adımları

1. Controller dosyasını oluştur, metotları **birebir taşı** — davranış
   değişikliği yok, yeniden adlandırma yok, "yol boyunca iyileştirme" yok.
2. `ArchlenceApp`'e delege metodu ekle:
   `def apply_theme(self, *a, **kw): return self._theme.apply_theme(*a, **kw)`
3. `ArchlenceApp.__init__`/`build`'de controller'ı kur.
4. Tam paket + dört kapı + `python -m compileall`.
5. **Uygulamayı gerçekten aç**, ilgili ekranı gör. Bu adım atlanamaz: `.kv`
   bağları yalnız çalışma zamanında çözülüyor.
6. Taşınan her `app.<metot>` için `.kv`'de hâlâ çözülüyor mu — ölçerek
   doğrula (§4'teki kapı).

---

## 4. Önce yazılması gereken kapı

**YAZILDI — `tests/test_kv_app_surface.py`.** Aşağıdaki gereklilik
karşılandı; ayrıştırmanın önkoşulu artık açık değil.

Kapı `.kv` dosyalarını tarıyor, 40 benzersiz `app.<isim>` referansı buluyor ve
her birinin `ArchlenceApp`'te var olduğunu doğruluyor. Bilinen-bozuk duruma
karşı sınandı: `toggle_wealth_visibility` yeniden adlandırıldığında kırmızıya
döndü ve kırılmanın yerini (`ui/dashboard.kv:1579`) gösterdi.

Özgün gereklilik, kayıt için:

`tests/test_kv_app_surface.py` — `.kv` dosyalarını tarar, her `app.<isim>`
referansını çıkarır ve `ArchlenceApp` üzerinde o ismin GERÇEKTEN var olduğunu
doğrular (metot ya da property).

Bugün böyle bir kapı yok. Bu yüzden bir delege metodu yanlış yazılırsa hiçbir
şey uyarmaz — düğme sessizce ölür. Kapı olmadan bu ayrıştırmaya
**başlanmamalı**.

Kapı, bilinen-bozuk duruma karşı doğrulanmalı: mevcut bir `app.` metodu geçici
olarak yeniden adlandırıldığında kırmızıya dönmeli.

Bu tek başına küçük bir PR (dilim -1) ve ayrıştırma yapılmasa bile değerli:
`.kv`'nin app yüzeyini kalıcı olarak kilitler.

---

## 5. Bu planın KAPSAMINA GİRMEYENLER

Bilinçli sınırlar:

- **17 mixin taşınmıyor.** Kütlenin çoğu orada (`asset_mixin` tek başına 2032
  satır), ama mixin'ler `main.py`'nin uzunluğu sorununun parçası değil; ayrı
  dosyalarda ve kendi test kapsamları var. `ArchlenceApp`'in miras listesini
  kısaltmak ayrı ve daha büyük bir iş; bu plan bitince yeniden
  değerlendirilebilir.
- **Davranış değişikliği yok.** Hiçbir dilimde bir hata düzeltilmez, bir metot
  yeniden adlandırılmaz, bir imza değişmez. Ayrıştırma sırasında "bir de şunu
  düzeltelim" en sık geri tepme sebebidir; bulunan kusurlar ayrı issue olur.
- **`.kv` bölünmesi yok.** `dashboard.kv` 2.762 satır ve bu da bir sorun, ama
  farklı bir sorun. Kv'yi bölmek `#:include` semantiği ve kural çözümleme
  sırası demek — kendi planını hak eder.
- **`savings_mixin` (458 satır, 0 test dosyası)** — bu plan ona dokunmuyor, ama
  ölçüm sırasında ortaya çıktığı için kaydediliyor: test kapsamı olmayan en
  büyük mixin o. Ayrıştırmadan önce ya da bağımsız olarak kapsanması ayrı bir
  iş olarak değerlendirilmeli.

---

## 6. Durma koşulları

Ayrıştırma şu durumlarda **durdurulup geri alınır**, "sonra düzeltiriz"
denmez:

- Bir dilimde test paketinden biri kırmızıya döner ve sebebi taşımanın kendisi
  değil, gizli bir bağımlılıksa.
- `.kv` yüzey kapısı bir dilimde kırmızı verirse.
- Uygulama açılır ama ilgili ekran boş/ölü görünürse — bu turda öğrenildiği
  gibi, "açılıyor" ile "çalışıyor" aynı şey değil.
- İki dilim üst üste beklenenden çok daha fazla dosyaya dokunmayı gerektirirse:
  bu, seçilen dikişin yanlış olduğunun işaretidir; plan yeniden yazılır.

---

## 7. Bu planın maliyeti ve kazancı — dürüst değerlendirme

**Kazanç:** `main.py` 2.280 → ~650 satır. Her ekran davranışı kendi dosyasında,
adı ne yaptığını söylüyor. Yeni bir ekran eklemek `main.py`'ye dokunmayı
gerektirmez.

**Maliyet:** 6-7 PR, her biri tam doğrulama turu. Davranış kazancı **sıfır** —
kullanıcı hiçbir fark görmez. Risk sıfır değil: `.kv`'nin çalışma zamanı
bağları, testlerin yakalayamayacağı tek yer ve §4'teki kapı yazılmadan bu risk
kabul edilemez.

**Alternatif:** hiç yapmamak. `main.py` 2.280 satırla çalışıyor, testler yeşil,
kullanıcı etkilenmiyor. Bu madde sürüm engelleyici DEĞİL ve o sınıflandırma
doğru. Ayrıştırma bir bakım yatırımı, bir düzeltme değil.

**Önerim:** §4'teki kapıyı (`test_kv_app_surface.py`) ayrıştırmadan bağımsız
olarak **şimdi** yaz — küçük, tek başına değerli ve `.kv`'nin sessiz kırılma
riskini kalıcı kapatır. Ayrıştırmanın kalanını, `main.py`'ye dokunmayı
gerektiren bir sonraki gerçek iş çıkana kadar beklet; o zaman ilgili dilimi
önce yap.
