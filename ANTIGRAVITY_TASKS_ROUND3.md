# Antigravity IDE Görev Listesi — Tur 3: "Hesaplarım / Kartlarım" Arayüzü

> **DURUM: TAMAMLANDI (2026-07-20).** Görev 1 ve 2 uygulandı ve uçtan uca
> doğrulandı (`76d3cc7`, `b872730`). Ardından diyalog yerleşimi yeniden yazıldı:
> sekme geçişlerinde içeriğin başlığın üzerine taşması giderildi ve karanlık
> tema kontrastı düzeltildi. Görev 3 (işlem diyaloğuna hesap seçici) YAPILMADI,
> bir sonraki tura kaldı.

Bu turda YALNIZCA arayüz (widget + layout) işi var. Backend (veritabanı şeması,
bakiye matematiği, doğrulama, net servet hesabı) tamamlanmış ve testleri geçmiş
durumda — commit `768638a` ve `cae0671`.

## ⛔ Değiştirilmeyecek dosyalar

Aşağıdakiler mantık/hesaplama katmanıdır, bu turda **hiçbirine dokunma**:

- `services/account_service.py`
- `services/transaction_service.py`
- `database/db.py`, `database/init_db.py`
- `mixins/account_mixin.py` içindeki `commit_new_account`, `render_accounts`,
  `_update_account_summary`, `_build_account_card` metodları
- `tests/` altındaki hiçbir dosya

Sadece **`ui/dashboard.kv`** ve **`mixins/account_mixin.py::open_add_account_dialog`**
(tek bir metod gövdesi) düzenlenecek.

Her adımdan sonra `.venv/bin/python -m py_compile mixins/account_mixin.py` temiz
kalmalı.

---

## ✅ Görev 1 — `ui/dashboard.kv`: "Kartlarım" sekmesi *(tamamlandı)*

`MDBottomNavigation` altında şu an 4 sekme var: `home_tab` (satır ~303),
`assets_tab` (~729), `tools_tab` (~1207), `settings_tab` (~1431).
**`assets_tab` ile `tools_tab` arasına** beşinci bir sekme ekle.

Şablon olarak `assets_tab`'ın gövdesini (satır 729-760 civarı) birebir örnek al —
aynı `MDFloatLayout > MDBoxLayout > MDTopAppBar + AnchorLayout > ScrollView >
MDBoxLayout(adaptive_height)` iskeleti, aynı `padding: "24dp"` / `spacing: "24dp"`.

```
MDBottomNavigationItem:
    name: "accounts_tab"
    text: "Kartlarım"
    icon: "credit-card-multiple-outline"
    on_tab_press: app.render_accounts()
    ...
```

Sekmenin içine sırayla şunlar girecek:

**1a. Özet kartı (3 metrik).** `assets_tab`'daki "DÖNEM ÖZET KARTI" bloğunu
(satır 757-825) birebir aynı üslupta kopyala — 3 adet yan yana `MDCard`,
`height: "96dp"`, `spacing: "10dp"`, `radius: [20,20,20,20]`, `elevation: 0`,
`line_color: 0.8, 0.8, 0.8, 0.3`. Sadece etiketler ve id'ler farklı:

| Sıra | Başlık (Caption) | Değer etiketinin id'si | `md_bg_color` | Değer rengi |
|---|---|---|---|---|
| 1 | `Nakit` | `accounts_cash_label` | `0.85, 0.95, 0.88, 1` | `0.06, 0.55, 0.18, 1` |
| 2 | `Kart Borcu` | `accounts_debt_label` | `0.98, 0.88, 0.88, 1` | `0.78, 0.1, 0.1, 1` |
| 3 | `Net Servet` | `accounts_net_label` | `0.88, 0.94, 0.98, 1` | (varsayılan, `theme_text_color: "Primary"`) |

Üçünün de başlangıç `text`'i `"₺0,00"` olsun. **Bu id'ler birebir bu şekilde
olmalı** — `_update_account_summary` bu id'leri arıyor, farklı yazarsan özet
sessizce boş kalır.

**1b. "Hesap/Kart Ekle" butonu.**

```
MDRaisedButton:
    text: "+ HESAP / KART EKLE"
    pos_hint: {"center_x": .5}
    on_release: app.open_add_account_dialog()
```

**1c. Kart listesi konteyneri.** Kartları backend kendisi çizer; sen sadece boş
kabı ver:

```
MDBoxLayout:
    id: accounts_container
    orientation: "vertical"
    adaptive_height: True
    spacing: "12dp"
```

`id: accounts_container` **birebir** böyle olmalı — `render_accounts` bu id yoksa
sessizce hiçbir şey çizmez.

---

## ✅ Görev 2 — `open_add_account_dialog` diyaloğu *(tamamlandı, sonradan yerleşimi yeniden yazıldı)*

`mixins/account_mixin.py` içindeki `open_add_account_dialog` şu an tek satırlık
bir stub. Gövdesini diyaloğu kuracak şekilde doldur. Docstring'i **silme**,
sözleşmeyi orada anlatıyor.

Üslup örneği: `mixins/savings_mixin.py::add_funds_to_goal` (satır 142-189) —
`MDDialog(type="custom", content_cls=<MDBoxLayout>, buttons=[MDRaisedButton, ...])`.

### Formda olması gereken alanlar

| Alan | Widget | Not |
|---|---|---|
| Hesap türü | 2 adet `MDRaisedButton` ya da `MDSegmentedControl` | Seçenekler: **"Nakit / Vadesiz"** ve **"Kredi Kartı"**. Varsayılan seçili: Nakit/Vadesiz |
| Hesap adı | `MDTextField(hint_text="Hesap / Kart Adı")` | |
| Başlangıç bakiyesi | `MDTextField(hint_text="Başlangıç Bakiyesi (₺)", input_filter="float")` | Vadesiz seçiliyken görünür |
| Mevcut borç | `MDTextField(hint_text="Mevcut Borç (₺)", input_filter="float")` | Kredi kartı seçiliyken görünür. **Pozitif** girilir, işaret çevirme backend'de |
| Kart limiti | `MDTextField(hint_text="Toplam Limit (₺)", input_filter="float")` | Yalnızca kredi kartında |
| Kesim günü | `MDTextField(hint_text="Hesap Kesim Günü (1-31, opsiyonel)", input_filter="int")` | Yalnızca kredi kartında, boş bırakılabilir |

Tür değişince ilgili alanları göster/gizle: `savings_mixin` ve `debt_mixin`'de
kullanılan `height` + `opacity` toggle kalıbı yeterli (widget'ı yok etme, sadece
`height = 0` / `opacity = 0` yap) — `render_accounts`'taki boş-liste etiketinde de
aynı kalıp var.

### Butonlar

- **VAZGEÇ** — `md_bg_color=(0.8, 0.2, 0.2, 1)`, sadece `dialog.dismiss()`
- **KAYDET** — `md_bg_color=(0.18, 0.8, 0.25, 1)`, aşağıdaki çağrıyı yapar

### KAYDET'in yapacağı TEK çağrı

Doğrulama, hata mesajı (toast), diyaloğun kapatılması ve ekranın tazelenmesi
`commit_new_account` içinde **zaten var**. Kendi doğrulamanı yazma, `try/except`
ekleme, `AccountService`'i doğrudan çağırma:

```python
self.commit_new_account(
    name=self.acc_name_field.text,
    account_type="credit_card" if <kredi kartı seçili> else "checking",
    initial_balance=<vadesizde başlangıç bakiyesi, kartta MEVCUT BORÇ>,
    credit_limit=<kartta limit, vadesizde 0>,
    statement_date=<kesim günü metni ya da None>,
)
```

Boş bırakılan sayısal alanlar için `""` ya da `0` geçmen yeterli — backend
ikisini de tolere ediyor (`float(x or 0)`).

**Önemli:** diyalog nesnesini `self.account_dialog = dlg` şeklinde ata.
`commit_new_account` başarılı kayıttan sonra diyaloğu **buradan** kapatıyor;
atamazsan diyalog açık kalır. Kendi `dismiss()` çağrını KAYDET'e ekleme —
doğrulama hatasında diyaloğun açık kalması gerekiyor ki kullanıcı düzeltebilsin.

`commit_new_account` başarıda `True`, doğrulama hatasında `False` döner
(hatayı zaten toast ile göstermiştir).

---

## ⬜ Görev 3 — İşlem diyaloğuna hesap seçici *(YAPILMADI — sonraki tur)*

Şu an işlem ekleme `DEFAULT_ACCOUNT_ID` (=1) sabitini kullanıyor
(`mixins/transaction_mixin.py:157`). Kullanıcının karttan harcama yapabilmesi
için işlem diyaloğunda bir hesap seçici gerekiyor.

- `app.get_account_choices()` diye bir şey **YOK** — ihtiyacın olan liste
  `AccountService.get_accounts()` çağrısından gelir ve her eleman
  `{"id", "name", "type_label", ...}` içerir. Bu çağrıyı diyaloğu kuran yerde
  yapabilirsin, mantık değişikliği sayılmaz.
- Seçilen hesabın id'sini `TransactionService.add_transaction(account_id=...)`
  parametresine geçir; **başka hiçbir şeyi değiştirme**.
- Limit aşımı durumunda `add_transaction` `ValueError` fırlatıyor ve
  `transaction_mixin` bunu zaten yakalayıp mesajı toast ile gösteriyor —
  ek bir kontrol yazma.

Bu görevden emin değilsen atla; 1 ve 2 tamamlandığında özellik kullanılabilir
durumda olur.

---

## Bitince

`.venv/bin/python -m unittest tests.test_account_service` çalıştır — 11 test
**OK** kalmalı. Kalmıyorsa mantık katmanına dokunmuşsundur, geri al.

> Not: `tests.test_ids` bu turdan **önce de** kırıktı
> (`ui/dashboard.kv:1640`, `app.active_category_type` binding hatası). Senin
> eklediğin sekme yüzünden değil; düzeltmeye çalışma, o ayrı bir iş.

---

## Tur 3 sonrası: yerleşim ve kontrast düzeltmesi (2026-07-20)

Görev 2 uygulandıktan sonra sekme geçişlerinde elemanlar yukarı fırlayıp
başlığın üzerine biniyordu. Kök neden ölçülerek doğrulandı:

`inner` kutusu `adaptive_height=True` idi, yani tür değişince (1 alan ↔ 3 alan)
yüksekliği değişiyordu; `MDDialog` ise yüksekliğini yalnızca açılışta
hesapladığından büyüyen içerik yukarı taşıyordu. Ölçüm: **1 alan → 51dp,
3 alan → 193dp (+142dp)**.

Yapılanlar (`mixins/account_mixin.py::open_add_account_dialog`):

- [x] Değişen alanlar sabit yükseklikli `dynamic_container` (`DYNAMIC_H`, 3 alan
      için ayrılmış) içine hapsedildi; `inner` yüksekliği artık SABİT. Tür
      değişiminde yalnızca konteynerin içeriği değişiyor, yüksekliği değil.
      Ölçüldü: yeni yaklaşımda 1 ↔ 3 alan geçişinde fark **0dp**.
- [x] Alan başına `FIELD_SLOT` ayrıldı: `MDTextField` kendi yüksekliğini içeriden
      hesaplayıp dışarıdan verileni ezdiği ve doğrulama hatasında helper_text
      için büyüdüğü için, konteyner en kötü durumda bile taşmıyor.
- [x] Karanlık tema kontrastı: `hint_text_color_normal`, `helper_text_color_normal`,
      `text_color_normal` (+ focus ve `fill_color_normal`) her iki tema için
      açıkça veriliyor; `mode="fill"` alanların koyu dolgusunda hint metni artık
      okunuyor.
- [x] `spacing=dp(16)` ve `padding=dp(24)`; hiyerarşi Başlık → Sekmeler →
      Alanlar → Butonlar sırasında akıyor.

**Not:** Diyalog tamamen Python'da (imperatif) kuruluyor, ona ait bir KV bloğu
yok — KV tarafındaki tek parça `ui/dashboard.kv` içindeki `accounts_tab`. Diyalog
KV'ye taşınmadı; bu, davranışı değiştirmeyen büyük bir yeniden yapılandırma
olurdu.

### Açık kalan
- Görev 3: işlem ekleme diyaloğu hâlâ `DEFAULT_ACCOUNT_ID` kullanıyor; kullanıcı
  arayüzden hangi hesaptan/karttan harcadığını seçemiyor.
- KAYDET butonunun rengi `#5444E5` olarak koda gömülü; `41a11db` ile tema
  seçilebilir yapıldığı için standart temada da indigo görünüyor.
