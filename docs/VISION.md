# Archlence — ürün vizyonu ve kapsam

> Güncel durum için `CHANGELOG.md`, teknik plan için `docs/ROADMAP.md`,
> güvenlik/güvenilirlik özeti için `docs/SECURITY_RELIABILITY_STATUS.md`.

## Ürün

Archlence, **yerel ve çevrimdışı** çalışan bir kişisel finans masaüstü
uygulamasıdır. Veri kullanıcının makinesinde kalır; uygulama finansal kayıtları
bir sunucuya göndermez. Tutar ve açıklama alanları diskte şifreli tutulur.

Kapsam: hesaplar ve kredi kartları, gelir/gider işlemleri, bütçe planlama,
birikim hedefleri, portföy (hisse/altın/döviz/kripto) takibi, abonelik ve
tekrarlayan ödeme tespiti, bakiye geçmişi ve senaryo projeksiyonu.

## Marka

Ürün adı **Archlence**. Simge, marka mavisi (`#5444E5`) üzerine beyaz "A"
monogramıdır. Bu değer bilinçli olarak `ui/theme.py` içindeki
`ARCHLENCE_PRIMARY_HEX` ile **aynıdır**: simge ile uygulama teması ikinci,
yönetilmeyen bir marka rengine ayrışmasın diye.

`assets/icon_source.svg` tek kaynaktır; `icon.png` ve `icon.ico` ondan üretilir.
Tasarım kararı ampirik: önceki kimlikteki ince "ışın" biçimleri 48 piksel
(görev çubuğu/tepsi) boyutunda tamamen kayboluyor ve işaret okunmaz hâle
geliyordu. Dolu harf formu 16 piksele kadar okunabilir kalıyor. Simgeyi 1024
piksellik PNG'de değil, gerçek `.ico` karelerinde değerlendirin.

## Sürüm hattı ve "kararlı" ne demek

Şu anki hat **0.0.x — ön yayım**. Bu numara bir alçakgönüllülük ifadesi değil,
bir uyarıdır: paket kuruluyor ve çalışıyor, akışlar testle korunuyor, ama
uygulama hâlâ gerçek kullanımla sınanıyor. Gündelik finans takibi için
önerilmez.

Bir sürümün "kararlı" sayılabilmesi için gereken asgari koşullar:

- Kullanıcı verisini bozan bilinen bir hata bulunmaması — özellikle **girilen
  değerden farklı bir değer kaydeden** her türlü hata (bu sınıf hata bir finans
  uygulamasında tek başına kararlılık iddiasını geçersiz kılar).
- Yükseltme yolunun ölçülmüş olması: önceki sürümün profili yeni sürümle
  açıldığında veri korunuyor mu (`build-windows.yml` içindeki yükseltme smoke
  testi; taban sürüm tanımlı olmadığında bu kapı AÇIKÇA atlanır ve uyarı basar).
- Yedekleme/geri yükleme akışının doğrulanmış olması.
- Windows ve Linux paketlerinin gerçek makinede kurulup çalıştığının
  görülmüş olması.

"Kararlı", bir bankacılık/muhasebe sertifikasyonu anlamına gelmez; paket ve
kullanım kararlılığını, veri bütünlüğü ve kurtarma kapsamını tarif eder.

## Platform kapsamı

Windows ve Linux hedefleniyor. **macOS kapsam dışıdır** (`.dmg`/notarization
işleri ayrıca karar verilene kadar listede yok).

Paketler **imzasızdır**; Windows'ta SmartScreen uyarısı görülebilir. Kod imzalama
bilinçli olarak ertelenmiştir.

## Kalıcı mühendislik kararları

Bunlar pahalı öğrenildi; değiştirmeden önce gerekçeyi okuyun.

- **Paketleme Python sürümü 3.12'ye sabitlenmiştir** (yerel geliştirme daha
  yeni olabilir). Kivy + PyInstaller ikili/DLL uyumu test edilmemiş sürümlerde
  risk taşıyor. Gerekçe `build-windows.yml`/`build-linux.yml` içinde
  `setup-python` adımının yanında yazılıdır.
- **`collect_all("kivymd")` gerçek bir GL bağlamı ister.** SDL'in `dummy` video
  sürücüsü bunu karşılamaz — hiç GL yüzeyi sağlamaz. Linux tarafında `xvfb-run`
  (gerçek sanal X11 + Mesa llvmpipe) kullanılır; Windows tarafında ANGLE
  (`KIVY_GL_BACKEND=angle_sdl2`) gerekir.
- **Test paketi `run_tests.py` üzerinden koşturulur.** Doğrudan `python -m
  unittest` çağrısı headless ayarlarını atlar. Ayrıca koşucunun rapor akışı,
  Kivy'nin `sys.stderr`i ele geçirmesine karşı açıkça sabitlenmiştir.
- **Finansal okumalar fail-closed'dır.** Okunamayan bir kayıt `0` sayılmaz;
  ilgili metrik geçersiz/kısmi duruma geçer. Yanlış bir toplam göstermek,
  hiç göstermemekten daha kötüdür.

## Kapsam dışı (şimdilik)

Mobil sürüm, bulut senkronizasyonu, çok kullanıcılı/paylaşımlı bütçe, banka
entegrasyonu (open banking), otomatik dekont/fatura okuma.
