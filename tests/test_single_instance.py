import multiprocessing
import tempfile
import unittest
from pathlib import Path

from utils.single_instance import AlreadyRunningError, SingleInstanceLock


def _try_lock(path, queue):
    lock = SingleInstanceLock(path)
    try:
        lock.acquire()
    except AlreadyRunningError:
        queue.put("blocked")
    else:
        queue.put("acquired")
        lock.release()


class SingleInstanceLockTest(unittest.TestCase):
    def _context(self):
        methods = multiprocessing.get_all_start_methods()
        return multiprocessing.get_context(
            "fork" if "fork" in methods else "spawn"
        )

    def test_second_process_cannot_acquire_same_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "instance.lock")
            with SingleInstanceLock(path):
                context = self._context()
                queue = context.Queue()
                process = context.Process(
                    target=_try_lock, args=(path, queue)
                )
                process.start()
                process.join(5)
                self.assertFalse(process.is_alive())
                self.assertEqual(queue.get(timeout=1), "blocked")

    def test_lock_is_recoverable_after_owner_exits(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "instance.lock")
            context = self._context()
            queue = context.Queue()
            process = context.Process(
                target=_try_lock, args=(path, queue)
            )
            process.start()
            process.join(5)
            self.assertEqual(queue.get(timeout=1), "acquired")

            with SingleInstanceLock(path):
                self.assertTrue(Path(path).is_file())

    def test_context_releases_after_exception(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "instance.lock")
            with self.assertRaisesRegex(RuntimeError, "injected"):
                with SingleInstanceLock(path):
                    raise RuntimeError("injected")
            with SingleInstanceLock(path):
                pass


if __name__ == "__main__":
    unittest.main()
