"""Snapshot cache'inde üretici, tüketici ve silme aynı anahtar tipini kullanmalı.

NEDEN VAR: `_asset_data_cache["recent"]` sözlüğüne üretici tarafı
`recent[account["id"]]` ile yazıyor — `id` sqlite3'ten **int** geliyor. UI de
`recent.get(acc["id"])` ile aynı tipte okuyor. Ama kart silme yolu
`recent.pop(str(account_id), None)` yapıyordu: string anahtar hiçbir zaman
eşleşmediği için silinen hesabın işlemleri snapshot'ta KALIYORDU.

Kullanıcıya bugün yansımıyor, çünkü aynı işlemde hesap `accounts` listesinden
de çıkarılıyor ve UI yalnız o listeyi dolaşıyor — yani bayat girdi çizilmiyor.
Yine de snapshot, profili artık tarif etmeyen bir durum taşıyor; `recent` bir
gün `accounts` listesinden bağımsız tüketilirse bu sessiz bir stale-state
sorununa dönüşür.

DÜZELTME NOTU: bu bulgu ilk raporlanırken "silinen id yeniden kullanılırsa yeni
hesap eski işlemleri görür" gerekçesi de yazılmıştı. YANLIŞTI ve kaldırıldı:
`accounts` tablosu `id INTEGER PRIMARY KEY AUTOINCREMENT` kullanıyor, yani
SQLite silinen id'leri yeniden vermiyor. Şema okunmadan yazılmış bir iddiaydı.

Tip tarafı da bu testle birlikte kapatıldı: `_AssetDataCache` TypedDict'i
`recent` anahtarını `int` olarak yazıyor, yani aynı uyuşmazlık artık tip
denetiminden de geçemez.
"""

import unittest

import services.asset_service as asset_service


class RecentCacheKeyType(unittest.TestCase):

    def setUp(self):
        self._saved = asset_service._asset_data_cache
        self.addCleanup(self._restore)

    def _restore(self):
        asset_service._asset_data_cache = self._saved

    def _seed(self):
        asset_service._asset_data_cache = {
            "summary": {"cash": 100.0, "card_debt": 50.0, "net": 50.0},
            "accounts": [{"id": 42, "name": "Kart"}, {"id": 7, "name": "Nakit"}],
            "recent": {42: ["silinen-kartin-islemi"], 7: ["kalan-hesabin-islemi"]},
            "active_assets_result": None,
            "ready": True,
        }

    def test_deleting_an_account_drops_its_recent_entry(self):
        """ASIL HATA: silinen hesabın işlemleri snapshot'ta kalmamalı."""
        self._seed()
        asset_service.invalidate_asset_data_cache(
            deleted_account_id=42, deleted_card_debt=50.0)

        cache = asset_service._asset_data_cache
        self.assertNotIn(
            42, cache["recent"],
            "silinen hesabın recent girdisi snapshot'ta kaldı",
        )

    def test_other_accounts_keep_their_recent_entries(self):
        """Tamamlayıcı vaka: düzeltme fazlasını silmemeli."""
        self._seed()
        asset_service.invalidate_asset_data_cache(
            deleted_account_id=42, deleted_card_debt=50.0)

        cache = asset_service._asset_data_cache
        self.assertEqual(cache["recent"], {7: ["kalan-hesabin-islemi"]})
        self.assertEqual([a["id"] for a in cache["accounts"]], [7])

    def test_string_account_id_is_normalised(self):
        """Çağıran string verse bile int anahtar silinmeli.

        `invalidate_asset_data_cache` `deleted_account_id`'yi zaten
        `int(...)` ile normalize ediyor; bu test o normalizasyonun
        kaldırılmasını engelliyor.
        """
        self._seed()
        asset_service.invalidate_asset_data_cache(
            deleted_account_id="42", deleted_card_debt=50.0)
        self.assertNotIn(42, asset_service._asset_data_cache["recent"])


if __name__ == "__main__":
    unittest.main()
