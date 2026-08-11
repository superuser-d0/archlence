# Maintainer: Archlence contributors

pkgname=archlence-bin
pkgver=0.0.9
# `pkgver` arttığı için 1'e SIFIRLANDI. `pkgrel` yalnızca upstream sürümü aynı
# kalırken paketleme değiştiğinde artar (v0.0.7'de ölçeklenebilir ikon eklenince
# 2 olmuştu); yeni sürümle birlikte sayaç yeniden başlar.
pkgrel=1
pkgdesc="Local-first personal finance manager (prebuilt AppImage)"
arch=('x86_64')
url="https://github.com/superuser-d0/archlence"
license=('MIT')
# hicolor-icon-theme: ölçeklenebilir ikon `/usr/share/icons/hicolor/scalable`
# altına kuruluyor; o dizin yapısının sahibi bu paket.
depends=('fuse2' 'hicolor-icon-theme')
provides=('archlence')
conflicts=('archlence')
options=('!strip')

source=(
  "Archlence-${pkgver}-x86_64.AppImage::${url}/releases/download/v${pkgver}/Archlence-${pkgver}-x86_64.AppImage"
  "archlence.desktop::https://raw.githubusercontent.com/superuser-d0/archlence/v${pkgver}/assets/archlence.desktop"
  "archlence.png::https://raw.githubusercontent.com/superuser-d0/archlence/v${pkgver}/assets/icon.png"
  "archlence.svg::https://raw.githubusercontent.com/superuser-d0/archlence/v${pkgver}/assets/icon_source.svg"
  "LICENSE::https://raw.githubusercontent.com/superuser-d0/archlence/v${pkgver}/LICENSE"
)

# v0.0.9 HENÜZ YAYINLANMADI — aşağıdaki hash'ler PLACEHOLDER.
#
# `v0.0.9` etiketi yayınlandıktan SONRA, v0.0.4-v0.0.8'de izlenen yöntemle
# doldurulacak: AppImage'ı indirip sha256'sını DOĞRUDAN hesaplayıp yayınlanan
# SHA256SUMS.txt ve GitHub asset digest'i ile karşılaştırmak; diğer dördünü hem
# `git cat-file blob v0.0.9:<yol>` ile hem raw.githubusercontent'ten alıp
# eşleştirmek. Sonuç `makepkg --verifysource` ile depo dışında doğrulanmalı.
#
# BİLEREK geçersiz (tamamı sıfır) placeholder, 'SKIP' DEĞİL: 'SKIP' makepkg'de
# doğrulamayı tamamen KAPATIR ve indirilen her dosyayı sessizce kabul eder.
# Geçersiz bir hash ise gerçek değerler yazılana kadar makepkg'i GÜVENLİ
# şekilde, yüksek sesle başarısız kılar.
#
# SIRA ÖNEMLİ: bu dizi `source` ile POZİSYON POZİSYON eşleşir, isimle değil.
#
# DİKKAT — her sürümde tekrar eden tuzak: SON DÖRT hash sürümler arası AYNI
# kalır (desktop dosyası, iki ikon, LICENSE değişmiyor), yalnızca AppImage'ın
# hash'i değişir (v0.0.6 e37bcb57..., v0.0.7 ba33aa5b..., v0.0.8 770539c5...).
# Bu, eski diziyi olduğu gibi taşımayı zararsız gösteriyor — DEĞİL: kopyalanan
# bir dizi dört dosyayı DOĞRU, asıl gönderilen ikiliyi YANLIŞ doğrular ve
# makepkg beş satırın hepsini yeşil basar. O yüzden beşi de sıfırlandı.
sha256sums=(
  '0000000000000000000000000000000000000000000000000000000000000000'
  '0000000000000000000000000000000000000000000000000000000000000000'
  '0000000000000000000000000000000000000000000000000000000000000000'
  '0000000000000000000000000000000000000000000000000000000000000000'
  '0000000000000000000000000000000000000000000000000000000000000000'
)

package() {
  install -Dm755 \
    "${srcdir}/Archlence-${pkgver}-x86_64.AppImage" \
    "${pkgdir}/opt/archlence/Archlence.AppImage"

  install -Dm644 "${srcdir}/archlence.desktop" \
    "${pkgdir}/usr/share/applications/archlence.desktop"
  sed -i 's/^Exec=.*/Exec=archlence/' \
    "${pkgdir}/usr/share/applications/archlence.desktop"

  install -Dm644 "${srcdir}/archlence.png" \
    "${pkgdir}/usr/share/icons/hicolor/1024x1024/apps/archlence.png"
  # Ölçeklenebilir sürüm: 1024x1024 PNG küçük boyutlara (panel, görev
  # çubuğu, bildirim) indirildiğinde bulanıklaşıyor. `scalable` dizinini
  # gören masaüstleri her boyutu SVG'den üretir.
  install -Dm644 "${srcdir}/archlence.svg" \
    "${pkgdir}/usr/share/icons/hicolor/scalable/apps/archlence.svg"
  install -Dm644 "${srcdir}/LICENSE" \
    "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"

  install -d "${pkgdir}/usr/bin"
  printf '%s\n' '#!/bin/sh' \
    'exec /opt/archlence/Archlence.AppImage "$@"' \
    > "${pkgdir}/usr/bin/archlence"
  chmod 755 "${pkgdir}/usr/bin/archlence"
}
