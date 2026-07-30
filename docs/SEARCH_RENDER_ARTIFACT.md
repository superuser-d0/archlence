# Arama alanı render artefact’ı

## Kök neden

İki çizginin kaynakları birbirinden bağımsızdı:

1. KivyMD 1.2 `MDTextField mode: "round"` zeminini iki yarım `Ellipse` ve
   aralarında bir `Rectangle` ile çiziyor. Sağ elipsin düz çapı orta
   rectangle tarafından kapatılmadığı için elipsin merkezinde tam yükseklikte
   daha koyu bir birleşim kolonu oluşuyordu. Bu cursor değildi: canlı SDL
   ölçümünde alan `focus=False`, cursor soldayken çizgi sağ kapak merkezinde
   kaldı.
2. Ana sayfa `ScrollView` bileşeninin varsayılan `bar_width=2` göstergesi,
   içeriğin sağında pencere kenarına yapışık bağımsız bir çizgi gibi
   görünüyordu.

## Çözüm

Arama alanı tek bir `RoundedRectangle` yüzey ve tek bir yuvarlatılmış
`SmoothLine` sınır kullanan `SearchBar` bileşenine dönüştürüldü. İçteki
standart `TextInput`, cursor’ı yalnız gerçek focus sırasında çizer. Rastgele
piksel ofseti veya arka plan rengiyle örtme kullanılmadı. Ana sayfanın
görsel scrollbar’ı kapatıldı; mouse wheel/touch kaydırma davranışı korundu.

`scripts/dev/verify_search_bar_visual.py` açık/koyu, focus/unfocus ve pencere
yeniden boyutlandırma senaryolarını gerçek SDL penceresinde yakalar. Sağ kapak
merkezindeki kesintisiz kontrast kolonunu ve pencerenin son iki kolonundaki
scrollbar çizgisini ölçer. Yüksek DPI koşusu
`KIVY_METRICS_DENSITY=2` ortam değişkeniyle ayrıca çalıştırılır.
