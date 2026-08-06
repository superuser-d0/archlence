# Maintainer: Archlence contributors

pkgname=archlence-bin
pkgver=0.0.8
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

# v0.0.8 kaynakları üç bağımsız yoldan doğrulandı:
#   - AppImage: doğrudan indirilip yerelde sha256'sı hesaplandı; yayın
#     manifesti (SHA256SUMS.txt) ve GitHub'ın asset digest'i ile eşleşti.
#   - Diğer dördü: hem `git cat-file blob v0.0.8:<yol>` hem
#     raw.githubusercontent'ten v0.0.8 etiketiyle alınıp karşılaştırıldı.
# Sonuç `makepkg --verifysource` ile depo dışında sınandı: beşi de Passed.
#
# SIRA ÖNEMLİ: bu dizi `source` ile POZİSYON POZİSYON eşleşir, isimle değil.
#
# DİKKAT — her sürümde tekrar eden tuzak: aşağıdaki SON DÖRT hash v0.0.7'deki
# değerlerin BİREBİR AYNISI, çünkü desktop dosyası, iki ikon ve LICENSE
# içerikleri sürümler arası değişmiyor. Bu, eski diziyi olduğu gibi taşımayı
# zararsız gösteriyor — DEĞİL: yalnızca AppImage'ın hash'i değişir
# (v0.0.6 e37bcb57..., v0.0.7 ba33aa5b..., v0.0.8 770539c5...). Kopyalanan bir
# dizi dört dosyayı DOĞRU, asıl gönderilen ikiliyi YANLIŞ doğrular ve makepkg
# beş satırın hepsini yeşil basar.
sha256sums=(
  '770539c58f2b596464d6710954f019069342dacae84480ff8d048e4b062c66d5'
  '4cf21f62e33e87cf69cd015fb9148dbe99badaf75c3caf3b87db1b8813089d71'
  '1df0fe8c33ba3b13cee650cab7e254964e18acbd27c330dce19ac0aaf7110b9f'
  'e27e0925f3d0d33dcd212391b038c04dbc89020f212d145bfdca6f0600b2e9ec'
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
