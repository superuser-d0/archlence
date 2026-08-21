"""bind_card_tap testleri (Aşama 2, madde 1.6/1.7).

HATA: `MDCard.bind(on_release=...)` sessizce hiç ateşlenmiyordu — MDCard'ın
`ripple_behavior=True`'su yalnızca `RectangularRippleBehavior`'dan gelen
GÖRSEL dalga efektini sağlıyor, `ButtonBehavior`'ı miras almıyor ve
`on_press`/`on_release` olaylarını hiç dispatch etmiyor (doğrulandı:
`'on_release' in MDCard.__events__` -> `False`). Bu paket ui/theme.py::
bind_card_tap'in gerçek bir dokunuş algılaması kurduğunu kilitler.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("KIVY_NO_ARGS", "1")


class _FakeCard:
    """`collide_point`/`disabled`/`bind(on_touch_up=...)` sağlayan sahte kart."""

    def __init__(self, collides=True, disabled=False):
        self._collides = collides
        self.disabled = disabled
        self._touch_up_handler = None

    def collide_point(self, x, y):
        return self._collides

    def bind(self, **kwargs):
        if "on_touch_up" in kwargs:
            self._touch_up_handler = kwargs["on_touch_up"]

    def fire_touch_up(self, pos=(0, 0), touch=None):


        if touch is None:
            touch = mock.Mock(pos=pos, ud={})
        return self._touch_up_handler(self, touch)


class BindCardTapTest(unittest.TestCase):
    def test_tap_within_bounds_calls_callback(self):
        from ui.theme import bind_card_tap
        card = _FakeCard(collides=True)
        callback = mock.Mock()
        bind_card_tap(card, callback)
        card.fire_touch_up()
        callback.assert_called_once_with()

    def test_tap_outside_bounds_does_not_call_callback(self):
        from ui.theme import bind_card_tap
        card = _FakeCard(collides=False)
        callback = mock.Mock()
        bind_card_tap(card, callback)
        card.fire_touch_up()
        callback.assert_not_called()

    def test_disabled_card_does_not_call_callback(self):
        from ui.theme import bind_card_tap
        card = _FakeCard(collides=True, disabled=True)
        callback = mock.Mock()
        bind_card_tap(card, callback)
        card.fire_touch_up()
        callback.assert_not_called()

    def test_same_touch_dispatched_twice_only_fires_callback_once(self):
        """DÜZELTME (2026-07-29 — "her şeye tıklasam iki kez açılıyor"):
        `ripple_behavior`li bir MDCard'ın kendi ButtonBehavior zinciri
        dokunuşu `touch.grab()` ile yakalıyor; Kivy'nin gerçek olay döngüsü
        aynı `on_touch_up`'ı hem normal ağaç gezinmesiyle HEM DE
        `touch.grab_list` redispatch'iyle AYRI AYRI çağırıyor — yani aynı
        `touch` nesnesi bu handler'a iki kez ulaşıyor. Kullanıcı gerçek
        cihazda bunu "her şeye tıklasam iki kez açılıyor, çift sekme
        şeklinde" diye bildirdi. `touch.ud` tabanlı tekilleştirme bunu
        önlemeli: aynı touch nesnesiyle iki dispatch, tek çağrı üretmeli."""
        from ui.theme import bind_card_tap
        card = _FakeCard(collides=True)
        callback = mock.Mock()
        bind_card_tap(card, callback)

        shared_touch = mock.Mock(pos=(0, 0), ud={})
        card.fire_touch_up(touch=shared_touch)   # normal propagation
        card.fire_touch_up(touch=shared_touch)   # grab_list redispatch (AYNI touch)

        callback.assert_called_once_with()

    def test_different_touches_each_fire_the_callback(self):
        """Tekilleştirme dokunuş BAŞINA olmalı — iki AYRI gerçek tıklama
        (iki farklı touch nesnesi) callback'i iki kez tetiklemeli, aksi
        halde kart ilk tıklamadan sonra kalıcı olarak ölü kalırdı."""
        from ui.theme import bind_card_tap
        card = _FakeCard(collides=True)
        callback = mock.Mock()
        bind_card_tap(card, callback)

        card.fire_touch_up(touch=mock.Mock(pos=(0, 0), ud={}))
        card.fire_touch_up(touch=mock.Mock(pos=(0, 0), ud={}))

        self.assertEqual(callback.call_count, 2)

    def test_handler_never_raises_regardless_of_return_value(self):
        """Ripple'ın kendi on_touch_up'ı bağımsız çalışmaya devam etmeli;
        handler'ımız her koşulda False dönüp zinciri bloklamamalı."""
        from ui.theme import bind_card_tap
        card = _FakeCard(collides=True)
        bind_card_tap(card, mock.Mock())
        self.assertFalse(card.fire_touch_up())


if __name__ == "__main__":
    unittest.main()
