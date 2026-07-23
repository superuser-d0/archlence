# Finora

Kişisel finans takibi için **yerel-öncelikli (local-first)**, Python + SQLite
tabanlı bir masaüstü uygulaması. Kivy/KivyMD ile inşa edilmiş, sıradan bir
harcama takip aracının ötesinde **"premium bankacılık"** hissiyatını
hedefleyen bir arayüze sahip.

> 🚧 Aktif geliştirme aşamasında. Kaynak kod şu an **özel (private)**
> tutuluyor — bu repo projenin vitrin/tanıtım sayfasıdır.

## Öne Çıkan Özellikler

- **Yerel-öncelikli mimari** — verileriniz cihazınızdan çıkmaz; bulut yok,
  üçüncü taraf sunucu yok.
- **Şifreli veri katmanı** — hassas alanlar AES-256-CBC ile şifrelenir.
- **Kredi kartı mantığı** — borç, işaretli (negatif) bakiye konvansiyonuyla
  modellenir; net servet hesaplaması tek bir `SUM` ile doğru çıkar.
- **İzole birikim hedefleri** — hedefe ayrılan para, ana hesaptan atomik
  olarak izole edilir; harcama olarak görünmez.
- **RK4 (4. derece Runge-Kutta) servet projeksiyonu** — mevcut gelir/gider
  ivmenize göre 30 günlük bir ODE simülasyonuyla varlık tahmini üretir.
- **Premium / Standart tema sistemi** — açık/koyu mod ve özel Indigo
  "Premium Banking" paleti arasında dinamik geçiş.
- **Otomatik abonelik radarı** — tekrarlayan işlemleri istatistiksel olarak
  tespit edip "sessiz sızıntı" adaylarını yüzeye çıkarır.
- **İstatistiksel anomali tespiti** — z-skoru tabanlı harcama sapması uyarıları.
- **Finansal Sağlık Skoru** — tasarruf oranı, borç oranı ve oynaklık
  bileşenlerinden hesaplanan, geçmişi saklanan bir skor.
- **Çoklu dil (TR/EN)** — yerel i18n katmanı ile arayüz dili değiştirilebilir.

## Yol Haritası

- [ ] Bakiye zaman makinesi (point-in-time geçmiş & diff)
- [ ] What-if senaryo sandbox'ı
- [ ] Windows paket dağıtımının tamamlanması (build pipeline eklendi, test ediliyor)

## Ekran Görüntüleri

_(yakında eklenecek)_

## Teknoloji

Python · SQLite · Kivy / KivyMD

## İletişim

Sorularınız veya ilginiz için: **support@finora.com**
