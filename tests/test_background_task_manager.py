import threading
import unittest

from services.background_task_manager import BackgroundTaskManager


class BackgroundTaskManagerTest(unittest.TestCase):
    def setUp(self):
        self.callbacks = []
        self.manager = BackgroundTaskManager(
            schedule=self.callbacks.append, max_workers=2
        )

    def tearDown(self):
        self.manager.shutdown()

    def _drain(self):
        while self.callbacks:
            self.callbacks.pop(0)()

    def test_old_result_cannot_overwrite_new_result(self):
        release_old = threading.Event()
        results = []
        old = self.manager.submit(
            "dashboard",
            lambda cancel: release_old.wait(2) or "old",
            on_success=results.append,
            on_error=lambda exc: self.fail(str(exc)),
        )
        new = self.manager.submit(
            "dashboard",
            lambda cancel: "new",
            on_success=results.append,
            on_error=lambda exc: self.fail(str(exc)),
        )
        new.result(2)
        release_old.set()
        old.result(2)
        self._drain()
        self.assertEqual(results, ["new"])

    def test_duplicate_can_be_coalesced(self):
        release = threading.Event()
        first = self.manager.submit(
            "prices",
            lambda cancel: release.wait(2),
            on_success=lambda value: None,
            on_error=lambda exc: self.fail(str(exc)),
            replace=False,
        )
        second = self.manager.submit(
            "prices",
            lambda cancel: None,
            on_success=lambda value: None,
            on_error=lambda exc: self.fail(str(exc)),
            replace=False,
        )
        self.assertIs(first, second)
        release.set()
        first.result(2)

    def test_closed_screen_drops_callback(self):
        results = []
        future = self.manager.submit(
            "screen",
            lambda cancel: 42,
            on_success=results.append,
            on_error=lambda exc: self.fail(str(exc)),
            is_target_alive=lambda: False,
        )
        future.result(2)
        self._drain()
        self.assertEqual(results, [])

    def test_error_is_marshaled_to_error_callback(self):
        errors = []

        def fail(cancel):
            raise ValueError("worker failed")

        future = self.manager.submit(
            "error",
            fail,
            on_success=lambda value: self.fail("unexpected success"),
            on_error=errors.append,
        )
        future.result(2)
        self._drain()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)

    def test_cancel_and_shutdown_drop_callbacks(self):
        release = threading.Event()
        results = []
        future = self.manager.submit(
            "slow",
            lambda cancel: release.wait(2),
            on_success=results.append,
            on_error=lambda exc: results.append(exc),
        )
        self.manager.cancel("slow")
        release.set()
        future.result(2)
        self._drain()
        self.assertEqual(results, [])

        future = self.manager.submit(
            "shutdown",
            lambda cancel: 1,
            on_success=results.append,
            on_error=lambda exc: results.append(exc),
        )
        future.result(2)
        self.manager.shutdown()
        self._drain()
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
