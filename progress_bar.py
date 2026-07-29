import sys
import threading

class ProgressBar:
    def __init__(self, width: int = 40, accept_every : int = 1):
        self.width = width
        self.accept_every = accept_every
        self._lock = threading.Lock()
        self._last_length = 0
        self.accepted = 0

    def update(self, value: float, label: str = ""):
        self.accepted = (self.accepted + 1) % self.accept_every
        if self.accepted != 0:
            return
        value = max(0.0, min(1.0, value))
        real_width = self.width - len(str(label)) - 13
        with self._lock:
            filled = int(real_width * value)
            bar = "█" * filled + "-" * (real_width - filled)
            percent = value * 100
            text = f"\r[{bar}] {percent:6.2f}%"
            if label:
                text += f" | {label}"
            if len(text) < self._last_length:
                text += " " * (self._last_length - len(text))
            self._last_length = len(text)
            sys.stdout.write(text)
            sys.stdout.flush()
    def finish(self, label: str = "Done"):
        self.update(1.0, label)
        print()