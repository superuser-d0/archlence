# Archlence

Kişisel finans takibi için **yerel-öncelikli (local-first)**, Python + SQLite
tabanlı bir masaüstü uygulaması. Kivy/KivyMD ile inşa edilmiş, sıradan bir
harcama takip aracının ötesinde **"premium bankacılık"** hissiyatını
hedefleyen bir arayüze sahip.

> 🚧 Aktif geliştirme aşamasında. Kaynak kod şu an **özel (private)**
> tutuluyor — bu repo projenin vitrin/tanıtım sayfasıdır.
>

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
- **What-if senaryo sandbox'ı** — gelir/gider yüzde değişimi ve özel ufuk
  parametreleriyle taban senaryoya karşı karşılaştırmalı projeksiyon.
- **Bakiye zaman makinesi** — point-in-time geçmiş bakiye sorgusu ve iki
  tarih arası diff/karşılaştırma.
- **Premium / Standart tema sistemi** — açık/koyu mod ve özel Indigo
  "Premium Banking" paleti arasında dinamik geçiş, tercih kalıcı.
- **Otomatik abonelik radarı** — tekrarlayan işlemleri istatistiksel olarak
  tespit edip "sessiz sızıntı" adaylarını yüzeye çıkarır; haftalık/iki
  haftalık/aylık/üç aylık/yıllık periyotları otomatik takibe alabilir.
- **İstatistiksel anomali tespiti** — z-skoru tabanlı harcama sapması
  uyarıları, kalıcı olarak gizlenebilir.
- **Finansal Sağlık Skoru** — tasarruf oranı, borç oranı ve oynaklık
  bileşenlerinden hesaplanan, geçmişi saklanan ve trend grafiğiyle
  gösterilen bir skor.
- **Çoklu dil (TR/EN)** — yerel i18n katmanı ile arayüz dili değiştirilebilir.

## Yol Haritası

- [x] Otomatik abonelik radarı ve istatistiksel anomali tespiti
- [x] Finansal Sağlık Skoru (hesaplama, kalıcılık, trend grafiği)
- [x] Bakiye zaman makinesi (point-in-time geçmiş & diff)
- [x] What-if senaryo sandbox'ı
- [ ] Windows paket dağıtımının tamamlanması (build pipeline var, ikon ve
      smoke test ekleniyor)
- [ ] Linux paketleme (AppImage)

## Ekran Görüntüleri

_(yakında eklenecek)_

## Teknoloji

Python · SQLite · Kivy / KivyMD

## İletişim

Sorularınız veya ilginiz için: **support@archlence.com**
