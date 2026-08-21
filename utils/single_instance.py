"""Cross-platform, OS-released exclusive lock for one Archlence profile."""

import os
import sys
from pathlib import Path


_SENTINEL_BYTE = b"\0"
_PID_OFFSET = 1
_PID_FIELD_WIDTH = 32


class AlreadyRunningError(RuntimeError):
    """Another process owns the same profile lock."""


class SingleInstanceLock:
    def __init__(self, lock_path):
        self.path = Path(lock_path)
        self._stream = None

    @staticmethod
    def _lock_sentinel(stream):
        """Dosyanın 0. baytı üzerine bloklamayan özel kilit koyar."""
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock_sentinel(stream):
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def acquire(self):
        if self._stream is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)


        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        stream = os.fdopen(descriptor, "r+b")
        try:


            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(_SENTINEL_BYTE)
                stream.flush()

            self._lock_sentinel(stream)
        except (OSError, BlockingIOError) as exc:
            stream.close()
            raise AlreadyRunningError(
                "Archlence bu kullanıcı profili için zaten çalışıyor."
            ) from exc


        stream.seek(_PID_OFFSET)
        stream.write(
            str(os.getpid()).encode("ascii").ljust(_PID_FIELD_WIDTH, b" ")
        )
        stream.flush()
        os.fsync(stream.fileno())
        self._stream = stream

    def release(self):
        if self._stream is None:
            return
        stream, self._stream = self._stream, None
        try:
            try:
                self._unlock_sentinel(stream)
            except OSError:


                pass
        finally:
            stream.close()

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
