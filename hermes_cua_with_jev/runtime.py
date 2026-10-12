"""A host-wide lease shared by every profile of this plugin (POSIX)."""
import fcntl
import os
from pathlib import Path


class Busy(Exception):
    pass


class Uncertain(Exception):
    pass


class DesktopLease:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.pending = self.directory / 'uncertain'
        self.fd = None

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.fd = os.open(self.directory / 'desktop.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            self.fd = None
            raise Busy from None
        return self

    def require_settled(self):
        if self.pending.exists():
            raise Uncertain

    def before_mutation(self):
        fd = os.open(self.pending, os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, b'An action may still be in flight. Inspect and reconcile before more input.\n')
            os.fsync(fd)
        finally:
            os.close(fd)

    def after_mutation(self):
        self.pending.unlink(missing_ok=True)

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
