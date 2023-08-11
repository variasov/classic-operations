from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from types import TracebackType
from typing import Any, Callable, List, Optional, Type


Callback = Callable[[], None]


@dataclass
class Callbacks:
    persistent: List[Callback] = field(default_factory=list)
    transient: List[Callback] = field(default_factory=list)

    def add(self, callback: Callback):
        self.transient.append(callback)

    def handle(self):
        try:
            for callback in self.persistent:
                callback()

            while self.transient:
                callback = self.transient.pop(0)
                callback()
        except Exception:
            self.transient.clear()
            raise


class Operation:
    _on_complete: Callbacks
    _on_finish: Callbacks
    _on_cancel: Callbacks

    def __init__(
        self,
        on_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self._on_complete = Callbacks(on_complete or [])
        self._on_cancel = Callbacks(on_cancel or [])
        self._on_finish = Callbacks(on_finish or [])

    def on_start(self):
        pass

    def on_complete(self, callback: Callback) -> None:
        self._on_complete.add(callback)

    def on_cancel(self, callback: Callback) -> None:
        self._on_cancel.add(callback)

    def on_finish(self, callback: Callback) -> None:
        self._on_finish.add(callback)

    def start(self):
        pass

    def complete(self):
        try:
            self._on_complete.handle()
        except Exception:
            self.cancel()
            raise
        else:
            self.finish()

    def cancel(self):
        try:
            self._on_cancel.handle()
        finally:
            self.finish()

    def finish(self):
        self._on_finish.handle()

    def __enter__(self) -> 'Operation':
        self.start()
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

        return False


class NewOperation(ABC):

    @abstractmethod
    def new(self, **kwargs: Any) -> Operation: ...

    def __call__(self, **kwargs: Any) -> Operation:
        return self.new(**kwargs)
