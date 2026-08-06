# Maintainer: Archlence contributors

pkgname=archlence-bin
pkgver=0.0.7
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

# v0.0.7 kaynakları üç bağımsız yoldan doğrulandı:
#   - AppImage: doğrudan indirilip yerelde sha256'sı hesaplandı; yayın
#     manifesti (SHA256SUMS.txt) ve GitHub'ın asset digest'i ile eşleşti.
#   - Diğer üçü: hem `git cat-file blob v0.0.7:<yol>` hem
#     raw.githubusercontent'ten v0.0.7 etiketiyle alınıp karşılaştırıldı.
#
# DİKKAT — sonraki sürümde de geçerli: aşağıdaki SON ÜÇ hash v0.0.5 ve
# v0.0.6'dakiyle BİREBİR AYNI, çünkü desktop dosyası, ikon ve LICENSE
# içerikleri sürümler arası değişmiyor. Bu, eski diziyi olduğu gibi taşımayı
# zararsız gibi gösteriyor — DEĞİL: AppImage'ın hash'i her sürümde değişir
# (v0.0.6 e37bcb57..., v0.0.7 ba33aa5b...). Dördünün de aynı etiketten
# gelmesi gerekir; aksi halde üç dosya doğru, asıl önemli olan yanlış
# doğrulanır.
sha256sums=(
  'ba33aa5b9e46a6351ba95dea7f7c5993dd778164a3f7bd3d55ecde09f3f3f3dc'
  '4cf21f62e33e87cf69cd015fb9148dbe99badaf75c3caf3b87db1b8813089d71'
  '1df0fe8c33ba3b13cee650cab7e254964e18acbd27c330dce19ac0aaf7110b9f'
  'ecc8a7af57166c272c3b008712981c02f42898b6f2fad6889b7b51f9bf366c83'
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
