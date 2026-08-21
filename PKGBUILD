# Maintainer: Archlence contributors

pkgname=archlence-bin
pkgver=0.0.12

pkgrel=1
pkgdesc="Local-first personal finance manager (prebuilt AppImage)"
arch=('x86_64')
url="https://github.com/superuser-d0/archlence"
license=('MIT')

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

sha256sums=(
  '94ae79ce3e507ab70b70ec6ea00a8be231929b77914a7bbaebc7b2f27dad7740'
  '4cf21f62e33e87cf69cd015fb9148dbe99badaf75c3caf3b87db1b8813089d71'
  '1df0fe8c33ba3b13cee650cab7e254964e18acbd27c330dce19ac0aaf7110b9f'
  'e27e0925f3d0d33dcd212391b038c04dbc89020f212d145bfdca6f0600b2e9ec'
  '1684f5f89c0fb9943eaebf2b7ed20f2455a0c7b9b9ff195c3403f350418242eb'
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
