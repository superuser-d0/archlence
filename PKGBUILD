# Maintainer: Archlence contributors

pkgname=archlence-bin
pkgver=0.0.11
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

# v0.0.9 yayınlandı (2026-08-11); hash'ler v0.0.4-v0.0.8'deki yöntemle
# DOĞRULANDI, hiçbiri önceki sürümden kopyalanmadı.
#
# AppImage — üç bağımsız kaynak, üçü de aynı:
#   indirilen dosyanın sha256'sı (104.385.016 bayt), yayınlanan
#   SHA256SUMS.txt satırı, ve GitHub asset digest'i.
# Diğer dördü — iki bağımsız kaynak, dördünde de aynı:
#   `git cat-file blob v0.0.9:<yol>` ve raw.githubusercontent'ten indirme.
# Tamamı `makepkg --verifysource` ile depo dışında, temiz bir dizinde
# yeniden doğrulandı.
#
# SIRA ÖNEMLİ: bu dizi `source` ile POZİSYON POZİSYON eşleşir, isimle değil.
#
# DİKKAT — her sürümde tekrar eden tuzak: SON DÖRT hash sürümler arası AYNI
# kalır (desktop dosyası, iki ikon, LICENSE değişmiyor), yalnızca AppImage'ın
# hash'i değişir (v0.0.6 e37bcb57..., v0.0.7 ba33aa5b..., v0.0.8 770539c5...,
# v0.0.9 f8956d80...). Bu, eski diziyi olduğu gibi taşımayı zararsız
# gösteriyor — DEĞİL: kopyalanan bir dizi dört dosyayı DOĞRU, asıl gönderilen
# ikiliyi YANLIŞ doğrular ve makepkg beş satırın hepsini yeşil basar. Son
# dördünün v0.0.8'le aynı çıkması bu yüzden kopyalamanın gerekçesi değil,
# bağımsız hesabın teyididir.
#
# Bir sonraki sürümde: tag'den ÖNCE beşi de sıfıra çevrilir. 'SKIP' DEĞİL —
# 'SKIP' makepkg'de doğrulamayı tamamen KAPATIR ve indirilen her dosyayı
# sessizce kabul eder; geçersiz hash ise gerçek değerler yazılana kadar
# makepkg'i GÜVENLİ şekilde, yüksek sesle başarısız kılar.
sha256sums=(
  '5d2d61ed57858dde59f2fd13bae2016915f80024964a88e0edb12a8fc36809b2'
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
