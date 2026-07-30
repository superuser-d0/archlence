"""Cross-platform, OS-released exclusive lock for one Archlence profile."""

import os
import sys
from pathlib import Path


class AlreadyRunningError(RuntimeError):
    """Another process owns the same profile lock."""


class SingleInstanceLock:
    def __init__(self, lock_path):
        self.path = Path(lock_path)
        self._stream = None

    def acquire(self):
        if self._stream is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                if stream.read(1) == b"":
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(
                    stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
        except (OSError, BlockingIOError) as exc:
            stream.close()
            raise AlreadyRunningError(
                "Archlence bu kullanıcı profili için zaten çalışıyor."
            ) from exc
        stream.seek(0)
        stream.truncate()
        stream.write(f"{os.getpid()}\n".encode("ascii"))
        stream.flush()
        os.fsync(stream.fileno())
        self._stream = stream

    def release(self):
        if self._stream is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._stream.seek(0)
                msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._stream.close()
            self._stream = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


def notify_already_running(message):
    """Show a native Windows notice before Kivy/SQLite startup."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, "Archlence", 0x00000030
            )
            return
        except (AttributeError, OSError):
            pass
    print(message, file=sys.stderr)
