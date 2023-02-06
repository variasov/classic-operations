from abc import ABC, abstractmethod

import threading
from types import TracebackType
from typing import Any, Callable, List, Optional, Type

from .counter import Counter


Callback = Callable[[...], None]


class Operation:

    def __init__(
        self,
        on_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
        **kwargs: Any
    ):
        self.kwargs = kwargs
        # self._calls = Counter()

        self._on_complete_callbacks = on_complete or []
        self._on_cancel_callbacks = on_cancel or []
        self._on_finish_callbacks = on_finish or []

    def _handle_callbacks(self, callbacks: List[Callback]) -> None:
        for callback in callbacks:
            callback(**self.kwargs)

    def on_complete(self, callback) -> None:
        self._on_complete_callbacks.append(callback)

    def on_cancel(self, callback) -> None:
        self._on_cancel_callbacks.append(callback)

    def on_finish(self, callback) -> None:
        self._on_finish_callbacks.append(callback)

    def complete(self):
        try:
            self._handle_callbacks(self._on_complete_callbacks)
        except Exception:
            self.cancel()
            raise
        else:
            self.finish()

    def cancel(self):
        try:
            self._handle_callbacks(self._on_cancel_callbacks)
        finally:
            self.finish()

    def finish(self):
        self._handle_callbacks(self._on_finish_callbacks)

    def __enter__(self) -> 'Operation':
        # self._calls.increment()
        return self

    def __exit__(
        self, exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:

        # self._calls.decrement()
        #
        # if self._calls.is_last:
        if exc_type is None:
            self.complete()
        else:
            self.cancel()

        return False


class NewOperation(ABC):

    @abstractmethod
    def new(self, **kwargs: Any) -> Operation: ...

    def __call__(self, **kwargs: Any) -> Operation:
        # operation = getattr(self, 'operation', None)
        # if operation is None:
        #     self.operation = self.new(**kwargs)
        #
        # return self.operation

        return self.new(**kwargs)
