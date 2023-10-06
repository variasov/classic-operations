from types import TracebackType
from typing import List, Optional, Type

from .counter import ThreadSafeCounter as Counter
from .callbacks import ThreadSafeCallbacks as Callbacks, Callback


class Operation:
    _on_start: Callbacks
    _on_complete: Callbacks
    _on_finish: Callbacks
    _on_cancel: Callbacks

    def __init__(
        self,
        on_start: List[Callback] = None,
        on_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self._on_start = Callbacks(on_start or [])
        self._on_complete = Callbacks(on_complete or [])
        self._on_cancel = Callbacks(on_cancel or [])
        self._on_finish = Callbacks(on_finish or [])

        self._counter = Counter()

    def on_start(self, callback: Callback) -> None:
        self._on_start.add(callback)

    def on_complete(self, callback: Callback) -> None:
        self._on_complete.add(callback)

    def on_cancel(self, callback: Callback) -> None:
        self._on_cancel.add(callback)

    def on_finish(self, callback: Callback) -> None:
        self._on_finish.add(callback)

    def complete(self):
        assert not self._counter.is_zero

        try:
            self._on_complete.handle(suppress=True)
        finally:
            self._finish()

    def cancel(self):
        assert not self._counter.is_zero

        try:
            self._on_cancel.handle(suppress=True)
        finally:
            self._finish()

    def _finish(self):
        self._on_finish.handle(suppress=True)

    def __enter__(self) -> 'Operation':
        self._counter.increment()
        self._on_start.handle(suppress=False)
        return self

    def __exit__(
        self, exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:

        if exc_type is None:
            self.complete()
        else:
            self.cancel()

        self._counter.decrement()

        return False
