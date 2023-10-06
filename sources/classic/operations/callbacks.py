from dataclasses import dataclass, field
import threading

from typing import Callable, List

Callback = Callable[[], None]


@dataclass
class Callbacks:
    persistent: List[Callback] = field(default_factory=list)
    transient: List[Callback] = field(default_factory=list)

    def add(self, callback: Callback):
        self.transient.append(callback)

    def handle(self, suppress: bool):
        for callback in self.persistent:
            try:
                callback()
            except Exception:
                if not suppress:
                    self.transient.clear()
                    raise

        while self.transient:
            callback = self.transient.pop(0)
            try:
                callback()
            except Exception:
                self.transient.clear()
                raise


class ThreadSafeCallbacks(Callbacks, threading.local):
    pass
