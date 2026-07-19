# Antigravity IDE Görev Listesi — Tur 2 (mekanik / düşük risk)

Bu dosyadaki görevler zihinsel olarak kolay ama token/emek yoğun işlerdir; davranış
değiştirmezler. Mimari kararlar ve riskli refaktörler bu listeye GİRMEZ (onlar
Claude Code / Fable 5 tarafında yapılır). Her görev bağımsızdır, sırayla yapılabilir.
Her görevden sonra `python -m unittest discover -s tests` yeşil kalmalı.

## 1. Docstring tamamlama (davranışı DEĞİŞTİRMEDEN, sadece yorum ekle)

Örnek üslup için bkz. `mixins/transaction_mixin.py` ve `mixins/debt_mixin.py`
(modül üstü sınıf docstring'i + metod başına 1-3 satır "ne yapar + neden böyle").

- [ ] `mixins/calculator_mixin.py` — sınıf docstring'i eklendi; kalan tüm public
      metodlara (`calculate_compound`, `calculate_loan`, `export_plan_to_pdf`,
      `toggle_*`, `open_expense_dialog`, `add_custom_expense`, `update_expense_list_ui`,
      `remove_custom_expense`, `calculate_interest`, `show_payment_plan_table`)
      docstring ekle. Formüllerin (anüite, bileşik faiz) matematiğini bir satırla açıkla.
- [ ] `mixins/asset_mixin.py` — 1062 satır, 30 yorum. Her public metoda docstring;
      özellikle yfinance fiyat çekme, cache ve K/Z (kâr/zarar) hesap bölümlerine
      "veri nereden geliyor, hangi para biriminde" notu düş.
- [ ] `mixins/budget_mixin.py` ve `mixins/savings_mixin.py` — eksik metod
      docstring'lerini tamamla.
- [ ] `ui/charts.py` — her widget sınıfının başına "neyi çizer, hangi veri
      formatını bekler (ör. [(etiket, değer), ...])" docstring'i ekle.
- [ ] `ui/components.py` — her bileşen sınıfına 1 satırlık amaç docstring'i.
- [ ] `data/bist100.py` — dosya başına "liste ne zaman güncellendi, format nedir"
      açıklaması ekle.

## 2. Belirsiz / eski yorumları düzeltme

- [ ] Tüm dosyalarda `# print(...)` şeklinde yorumlanmış ölü debug satırlarını sil
      (ör. `main.py:265`).
- [ ] İngilizce/Türkçe karışık yorumları Türkçe'ye çevir (ör. `main.py:494`
      "Aylık Gelir Amacı card: display total income...", `main.py:765`
      "1. Main thread updates", `main.py:870`). Anlamı koru, sadece dili ve
      açıklayıcılığı düzelt.
- [ ] "Kapatıldı: Kasma sorunu" gibi bağlamsız notları "neden kapatıldı"
      bilgisiyle genişlet ya da ölü kodla birlikte sil.

## 3. Fonksiyon içi tekrarlanan import'ları toplama

`debt_mixin.py` ve `admin_screen.py`'de aynı modüller fonksiyon içinde defalarca
import ediliyor (`from kivymd.uix.label import MDLabel` vb.).

- [ ] Kivy/KivyMD import'larını dosya başına taşı (bunlar zaten main.py yüklenirken
      import edilmiş oluyor, başa almak davranış değiştirmez).
- [ ] DİKKAT — İSTİSNA: `database.db`, `services.*` gibi proje-içi import'lar
      fonksiyon içindeyse muhtemelen döngüsel import'u kırmak içindir; onlara
      DOKUNMA, yerinde bırak.

## 4. Küçük tutarlılık işleri

- [ ] `screens/admin_screen.py` — fonksiyon içindeki tekrarlı `from kivymd.toast
      import toast` satırlarını kaldır (dosya başında zaten var).
- [ ] Satır sonu boşlukları ve dosya sonundaki fazla boş satırları temizle
      (örn. `admin_screen.py` sonu).
- [ ] `main.py` içindeki çift import'ları tekilleştir: `NumericProperty` ve
      `StringProperty` iki kez import ediliyor (satır 56/59/63/182 civarı),
      `import os` iki kez (satır 1 ve 192). Sadece yinelenenleri sil.

## YAPMA (Fable 5'e bırak)

- main.py'nin bölünmesi / mixin mimarisinin değiştirilmesi
- Şifreleme (utils/crypto), veritabanı şeması, RK4 projeksiyon matematiği
- Thread/Clock akışlarının yeniden düzenlenmesi
- Herhangi bir dosya birleştirme/taşıma/silme

## 5. Mimari yol haritası — RecycleView geçişi (Fable 5 / Claude Code için, Antigravity'ye ATANMAZ)

2026-07-19 QA turunda arama kutularına debounce eklendi (bkz. `mixins/asset_mixin.py`
`_show_bist100_picker` / `_show_crypto_picker`, `_on_search` içindeki `Clock.schedule_once`
ile 300ms bekletme). BIST100/kripto seçici diyaloglarındaki ~100 kalemlik `MDList`
artık her tuş vuruşunda değil, yazma durduktan sonra tek seferde yeniden çiziliyor.

`MDList` → `RecycleView` geçişi bilinçli olarak YAPILMADI çünkü:
- `asset_history_list` (`ui/dashboard.kv:1036`) ve `recent_transactions_list`
  (`ui/dashboard.kv:685`) sorguları zaten `LIMIT 50` / `LIMIT 15` ile sınırlı
  (bkz. `database/db.py:get_asset_transaction_history`, `main.py` recent tx sorgusu)
  — 1000+ kayıt DB'de olsa da ekrana asla 50'den fazlası basılmıyor, bu yüzden
  bu iki liste için RecycleView'ın performans kazancı sınırlı.
- Her iki liste de tekil `MDList` değil; sabit yükseklikli `MDCard` + `ScrollView`
  içine iç içe yerleştirilmiş, kendi bağımsız viewport'u yok. RecycleView'ın
  kendi kaydırma/viewport yönetimini devralması için üst KV hiyerarşisinin
  (özellikle `asset_history_list`'i saran 320dp sabit `MDCard`) yeniden
  tasarlanması gerekir.
- Satır render mantığı: dinamik logo indirme (`_prefetch_asset_logos`), markup'lı
  K/Z renklendirmesi, `MDSeparator` araya ekleme, dinamik kart yüksekliği
  hesaplama (`render_asset_history` sonundaki `parent_card.height` bloğu) —
  bunların hepsi RecycleView'ın `viewclass`/`RecycleDataViewBehavior` modeline
  taşınmalı; mekanik bir port değil, tam bir yeniden yazım gerektiriyor.

Gerçek risk `render_active_assets` (`mixins/asset_mixin.py:1208`,
`active_assets_container`, `ui/dashboard.kv:994`) — bu tek liste SORGU
LİMİTİ YOK, kullanıcının tuttuğu tüm aktif varlıkları basıyor. Pratikte bir
kişi 1000+ farklı varlık tutmaz ama teorik tavan burada. İleride bu listeye
dokunulacaksa öncelik sırası:
1. `active_assets_container`'ı RecycleView'a taşı (limitsiz olan tek liste).
2. Gerekirse `asset_history_list` / `recent_transactions_list`'i de taşı,
   ama önce LIMIT değerini büyütme ihtiyacı doğarsa (ör. kullanıcı "tüm
   geçmişi göster" isterse) yapılmalı — şu an gerek yok.
