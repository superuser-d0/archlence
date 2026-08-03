# Maintainer: Archlence contributors

pkgname=archlence-bin
pkgver=0.0.4
pkgrel=1
pkgdesc="Local-first personal finance manager (prebuilt AppImage)"
arch=('x86_64')
url="https://github.com/superuser-d0/archlence"
license=('MIT')
depends=('fuse2')
provides=('archlence')
conflicts=('archlence')
options=('!strip')

source=(
  "Archlence-${pkgver}-x86_64.AppImage::${url}/releases/download/v${pkgver}/Archlence-${pkgver}-x86_64.AppImage"
  "archlence.desktop::https://raw.githubusercontent.com/superuser-d0/archlence/v${pkgver}/assets/archlence.desktop"
  "archlence.png::https://raw.githubusercontent.com/superuser-d0/archlence/v${pkgver}/assets/icon.png"
  "LICENSE::https://raw.githubusercontent.com/superuser-d0/archlence/v${pkgver}/LICENSE"
)

# DİKKAT: Bu hash'ler henüz v0.0.4'e güncellenmedi — release.yml v0.0.4
# varlıklarını yayınlayana kadar gerçek değerler bilinemez. Etiket push
# edilip GitHub Release + SHA256SUMS.txt yayınlandıktan SONRA, `updpkgsums`
# (pacman-contrib) veya SHA256SUMS.txt'ten elle güncellenmeli.
#
# BİLEREK geçersiz (tamamı sıfır) placeholder kullanılıyor, 'SKIP' DEĞİL:
# 'SKIP' makepkg'de doğrulamayı tamamen KAPATIR ve indirilen her dosyayı
# sessizce kabul eder — burada tam tersini istiyoruz. Geçersiz bir hash,
# gerçek değerler yazılana kadar `makepkg`'i GÜVENLİ şekilde, yüksek sesle
# başarısız kılar (checksum mismatch), yanlış/sahte bir ikili sessizce
# kurulmaz.
sha256sums=(
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
  install -Dm644 "${srcdir}/LICENSE" \
    "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"

  install -d "${pkgdir}/usr/bin"
  printf '%s\n' '#!/bin/sh' \
    'exec /opt/archlence/Archlence.AppImage "$@"' \
    > "${pkgdir}/usr/bin/archlence"
  chmod 755 "${pkgdir}/usr/bin/archlence"
}
