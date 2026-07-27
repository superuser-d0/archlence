import hashlib
import unittest

from security.security_service import SecurityService


class SecurityServiceTest(unittest.TestCase):
    def test_new_hash_is_argon2id_and_round_trips(self):
        pin_hash = SecurityService.hash_password("2468")
        self.assertTrue(pin_hash.startswith("$argon2id$"))
        self.assertTrue(SecurityService.verify_password("2468", None, pin_hash))

    def test_argon2id_hash_is_nondeterministic_but_both_verify(self):
        """Argon2id kendi rastgele tuzunu her çağrıda yeniden üretir — bu
        BİLEREK böyle (aynı PIN'in hep aynı hash'e düşmesi güvenlik açısından
        istenmez). Ham hash string'leri farklı olmalı, ikisi de doğrulanmalı."""
        first = SecurityService.hash_password("2468")
        second = SecurityService.hash_password("2468")
        self.assertNotEqual(first, second)
        self.assertTrue(SecurityService.verify_password("2468", None, first))
        self.assertTrue(SecurityService.verify_password("2468", None, second))

    def test_wrong_pin_is_rejected(self):
        pin_hash = SecurityService.hash_password("2468")
        self.assertFalse(
            SecurityService.verify_password("1357", None, pin_hash)
        )

    def test_generated_salt_has_128_bits_of_hex_entropy(self):
        """generate_salt() geriye dönük uyumluluk için korunuyor (bkz.
        modül docstring'i) — yeni Argon2id hash'leri bunu kullanmaz."""
        salt = SecurityService.generate_salt()
        self.assertEqual(len(salt), 32)
        int(salt, 16)

    def test_needs_upgrade_is_false_for_new_argon2id_hash(self):
        pin_hash = SecurityService.hash_password("2468")
        self.assertFalse(SecurityService.needs_upgrade(pin_hash))


class LegacySha256CompatibilityTest(unittest.TestCase):
    """Mevcut kullanıcıların diskteki hash'i hâlâ eski SHA-256 formatında.
    Bunlar Argon2id'ye geçirilmeden önce hâlâ doğru doğrulanabilmeli —
    aksi hâlde herkes PIN'ini unutmuş gibi kilit dışında kalırdı."""

    def _legacy_hash(self, pin, salt):
        payload = (str(salt) + str(pin)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def test_legacy_hash_still_verifies_correctly(self):
        salt = SecurityService.generate_salt()
        legacy_hash = self._legacy_hash("2468", salt)
        self.assertTrue(
            SecurityService.verify_password("2468", salt, legacy_hash)
        )

    def test_legacy_hash_rejects_wrong_pin(self):
        salt = SecurityService.generate_salt()
        legacy_hash = self._legacy_hash("2468", salt)
        self.assertFalse(
            SecurityService.verify_password("1357", salt, legacy_hash)
        )

    def test_needs_upgrade_is_true_for_legacy_hash(self):
        salt = SecurityService.generate_salt()
        legacy_hash = self._legacy_hash("2468", salt)
        self.assertTrue(SecurityService.needs_upgrade(legacy_hash))

    def test_lazy_migration_end_to_end(self):
        """Asıl senaryo: eski hash'le doğrula, needs_upgrade gördüğünde
        yeniden hash'le — sonuç artık Argon2id, hem eski hem yeni PIN'le
        (aynı PIN'le) doğrulanabilir olmalı."""
        salt = SecurityService.generate_salt()
        legacy_hash = self._legacy_hash("2468", salt)

        self.assertTrue(
            SecurityService.verify_password("2468", salt, legacy_hash)
        )
        self.assertTrue(SecurityService.needs_upgrade(legacy_hash))

        upgraded_hash = SecurityService.hash_password("2468")

        self.assertFalse(SecurityService.needs_upgrade(upgraded_hash))
        self.assertTrue(
            SecurityService.verify_password("2468", None, upgraded_hash)
        )

    def test_malformed_hash_fails_closed_not_crashes(self):
        """Ne SHA-256 ne Argon2id formatında bir kayıt (bozuk config) —
        çökme yok, güvenli tarafta kal: giriş reddedilir."""
        result = SecurityService.verify_password(
            "2468", "tuz", "ne-sha256-ne-argon2-olan-bir-string"
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
