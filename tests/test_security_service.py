import unittest

from security.security_service import SecurityService


class SecurityServiceTest(unittest.TestCase):
    def test_salted_hash_is_deterministic_for_same_pin_and_salt(self):
        salt = "0123456789abcdef"
        first = SecurityService.hash_password("2468", salt)
        second = SecurityService.hash_password("2468", salt)
        self.assertEqual(first, second)
        self.assertTrue(SecurityService.verify_password("2468", salt, first))

    def test_same_pin_has_different_hash_with_different_salts(self):
        first_salt = SecurityService.generate_salt()
        second_salt = SecurityService.generate_salt()
        self.assertNotEqual(first_salt, second_salt)
        self.assertNotEqual(
            SecurityService.hash_password("2468", first_salt),
            SecurityService.hash_password("2468", second_salt),
        )

    def test_wrong_pin_is_rejected(self):
        salt = SecurityService.generate_salt()
        pin_hash = SecurityService.hash_password("2468", salt)
        self.assertFalse(
            SecurityService.verify_password("1357", salt, pin_hash)
        )

    def test_generated_salt_has_128_bits_of_hex_entropy(self):
        salt = SecurityService.generate_salt()
        self.assertEqual(len(salt), 32)
        int(salt, 16)


if __name__ == "__main__":
    unittest.main()
