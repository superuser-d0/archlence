"""docs/ROADMAP.md Faz 1 madde 6 (PIN deneme sınırlama) — security.security_
service.LoginThrottle'ın saf mantığı. Hiçbir test gerçek saniye beklemez;
`now` her yerde enjekte ediliyor (bkz. LoginThrottle'ın kendi docstring'i)."""
import unittest

from security.security_service import LoginThrottle


class LockoutThresholdTest(unittest.TestCase):
    def test_no_lockout_below_threshold(self):
        for attempts in range(0, LoginThrottle.FAILED_ATTEMPT_THRESHOLD):
            state = {"failed_attempts": attempts, "last_failed_at": 1000.0}
            self.assertEqual(
                LoginThrottle.seconds_remaining(state, now=1000.0), 0.0,
                msg=f"{attempts} denemede kilit olmamalı",
            )
            self.assertFalse(LoginThrottle.is_locked(state, now=1000.0))

    def test_lockout_kicks_in_exactly_at_threshold(self):
        state = {
            "failed_attempts": LoginThrottle.FAILED_ATTEMPT_THRESHOLD,
            "last_failed_at": 1000.0,
        }
        self.assertTrue(LoginThrottle.is_locked(state, now=1000.0))
        self.assertGreater(
            LoginThrottle.seconds_remaining(state, now=1000.0), 0.0
        )

    def test_no_state_at_all_means_not_locked(self):
        """Hiç deneme kaydı yoksa (ilk giriş) kilit olmamalı."""
        self.assertFalse(LoginThrottle.is_locked(None))
        self.assertFalse(LoginThrottle.is_locked({}))


class ExponentialBackoffTest(unittest.TestCase):
    def test_duration_grows_with_each_additional_attempt(self):
        durations = [
            LoginThrottle._lockout_duration(n)
            for n in range(
                LoginThrottle.FAILED_ATTEMPT_THRESHOLD,
                LoginThrottle.FAILED_ATTEMPT_THRESHOLD + 5,
            )
        ]
        for earlier, later in zip(durations, durations[1:]):
            self.assertLess(earlier, later)

    def test_duration_caps_at_max_even_with_many_attempts(self):
        huge = LoginThrottle._lockout_duration(1000)
        self.assertEqual(huge, LoginThrottle.LOCKOUT_MAX_SECONDS)


class ClockInjectionTest(unittest.TestCase):
    """Asıl nokta: hiçbir gerçek time.sleep() olmadan 'zaman geçmesi'
    simüle edilebiliyor mu?"""

    def test_lockout_expires_after_enough_simulated_time_passes(self):
        state = LoginThrottle.record_failure({}, now=1000.0)
        for _ in range(LoginThrottle.FAILED_ATTEMPT_THRESHOLD - 1):
            state = LoginThrottle.record_failure(state, now=1000.0)
        self.assertTrue(LoginThrottle.is_locked(state, now=1000.0))

        duration = LoginThrottle._lockout_duration(state["failed_attempts"])
        still_locked_at = 1000.0 + duration - 1
        unlocked_at = 1000.0 + duration + 1

        self.assertTrue(LoginThrottle.is_locked(state, now=still_locked_at))
        self.assertFalse(LoginThrottle.is_locked(state, now=unlocked_at))

    def test_seconds_remaining_counts_down_linearly(self):
        state = {
            "failed_attempts": LoginThrottle.FAILED_ATTEMPT_THRESHOLD,
            "last_failed_at": 1000.0,
        }
        duration = LoginThrottle._lockout_duration(state["failed_attempts"])
        self.assertAlmostEqual(
            LoginThrottle.seconds_remaining(state, now=1000.0), duration,
        )
        self.assertAlmostEqual(
            LoginThrottle.seconds_remaining(state, now=1000.0 + duration / 2),
            duration / 2,
        )


class StateTransitionTest(unittest.TestCase):
    def test_record_failure_increments_and_does_not_mutate_input(self):
        original = {"failed_attempts": 2, "last_failed_at": 500.0}
        new_state = LoginThrottle.record_failure(original, now=999.0)

        self.assertEqual(original, {"failed_attempts": 2, "last_failed_at": 500.0})
        self.assertEqual(new_state["failed_attempts"], 3)
        self.assertEqual(new_state["last_failed_at"], 999.0)

    def test_record_failure_from_empty_state_starts_at_one(self):
        new_state = LoginThrottle.record_failure({}, now=1.0)
        self.assertEqual(new_state["failed_attempts"], 1)

    def test_record_success_resets_to_zero(self):
        state = LoginThrottle.record_success()
        self.assertEqual(state, {"failed_attempts": 0, "last_failed_at": None})
        self.assertFalse(LoginThrottle.is_locked(state, now=1_000_000.0))

    def test_full_cycle_lockout_then_success_resets_counter(self):
        """Uçtan uca: art arda başarısız denemeler kilide düşürür; sonraki
        başarılı giriş sayaçları sıfırlar, bir daha eski deneme sayısı
        birikmiş gibi davranmaz."""
        state = {}
        now = 0.0
        for _ in range(LoginThrottle.FAILED_ATTEMPT_THRESHOLD):
            state = LoginThrottle.record_failure(state, now=now)
        self.assertTrue(LoginThrottle.is_locked(state, now=now))

        state = LoginThrottle.record_success()
        self.assertFalse(LoginThrottle.is_locked(state, now=now))

        # Sıfırlama sonrası tek bir yeni başarısız deneme yeniden kilitlememeli.
        state = LoginThrottle.record_failure(state, now=now)
        self.assertFalse(LoginThrottle.is_locked(state, now=now))


if __name__ == "__main__":
    unittest.main()
