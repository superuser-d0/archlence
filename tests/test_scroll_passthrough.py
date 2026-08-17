"""Kart içi listeler kaydıramadıkları tekerlek olayını sayfaya bırakmalı.

NEDEN VAR: Kivy'nin `ScrollView.on_scroll_start`'ı, içerik görüntü alanına
tamamen sığsa bile tekerlek olayını işleyip `True` dönüyor
(kivy/uix/scrollview.py). Dış sayfa ScrollView'i çocuklarını önce dolaştığı
için olay orada bitiyor ve SAYFA KAYDIRILAMIYOR: imleç "Varlık Geçmişi"
listesinin (kart başlığının hemen altı) üzerindeyken tekerlek hiçbir şey
yapmıyordu. Aynı tuzak abonelik/gelir/borç/son işlem kartlarında da vardı.

`_WheelPassthroughMixin` kararı burada test ediliyor: kaydıracak yeri olmayan
ya da sınıra dayanmış liste `False` döner (ebeveyn devralır), gerçekten
kaydırabilen liste olayı kendinde tutar.
"""

import unittest

from ui.components import _WheelPassthroughMixin


class _Viewport:
    def __init__(self, height):
        self.height = height


class _FakeScroller(_WheelPassthroughMixin):
    """Mixin'in karar mantığı için grafiksiz vekil."""

    def __init__(self, viewport_height, height=300, scroll_y=1.0,
                 do_scroll_y=True, collides=True):
        self._viewport = _Viewport(viewport_height) if viewport_height is not None else None
        self.height = height
        self.scroll_y = scroll_y
        self.do_scroll_y = do_scroll_y
        self._collides = collides

    def collide_point(self, *_pos):
        return self._collides


class _Wheel:
    profile = ("pos", "button")

    def __init__(self, button):
        self.button = button
        self.pos = (0, 0)


class _Finger:
    profile = ("pos",)

    def __init__(self):
        self.pos = (0, 0)


class WheelPassthrough(unittest.TestCase):

    def test_content_fits_gives_wheel_to_parent(self):
        # Boş/kısa liste: 200dp içerik, 300dp kutu.
        scroller = _FakeScroller(viewport_height=200, height=300)
        for button in ("scrollup", "scrolldown"):
            with self.subTest(button=button):
                self.assertFalse(scroller._wheel_can_scroll(_Wheel(button)))

    def test_scrollable_content_keeps_the_wheel(self):
        scroller = _FakeScroller(viewport_height=900, height=300, scroll_y=0.5)
        for button in ("scrollup", "scrolldown"):
            with self.subTest(button=button):
                self.assertTrue(scroller._wheel_can_scroll(_Wheel(button)))

    def test_boundary_direction_goes_to_parent(self):
        # Tepedeyken yukarı, dipteyken aşağı: yön ebeveyne devredilir.
        at_top = _FakeScroller(viewport_height=900, height=300, scroll_y=1.0)
        self.assertFalse(at_top._wheel_can_scroll(_Wheel("scrolldown")))
        self.assertTrue(at_top._wheel_can_scroll(_Wheel("scrollup")))

        at_bottom = _FakeScroller(viewport_height=900, height=300, scroll_y=0.0)
        self.assertFalse(at_bottom._wheel_can_scroll(_Wheel("scrollup")))
        self.assertTrue(at_bottom._wheel_can_scroll(_Wheel("scrolldown")))

    def test_missing_viewport_or_locked_axis_gives_wheel_to_parent(self):
        self.assertFalse(
            _FakeScroller(viewport_height=None)._wheel_can_scroll(_Wheel("scrollup"))
        )
        self.assertFalse(
            _FakeScroller(viewport_height=900, do_scroll_y=False)
            ._wheel_can_scroll(_Wheel("scrollup"))
        )

    def test_non_wheel_and_non_colliding_touches_reach_the_base_class(self):
        # Parmak/sürükleme dokunuşu ile kutu dışındaki tekerlek, taban sınıfın
        # kendi defterini tutabilmesi için erken dönüşle kesilmemeli.
        scroller = _FakeScroller(viewport_height=200, height=300)
        self.assertTrue(scroller._wheel_can_scroll(_Finger()))

        outside = _FakeScroller(viewport_height=200, height=300, collides=False)
        self.assertTrue(outside._wheel_can_scroll(_Wheel("scrollup")))


if __name__ == "__main__":
    unittest.main()
