from types import TracebackType
from typing import Callable, List, Optional, Type, Iterable

from .local_dict import ScopedProperty


Callback = Callable[[], None]


class InnerOperation:

    def __init__(
        self,
        on_start: List[Callback] = None,
        on_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self.on_start = on_start or []
        self.on_complete = on_complete or []
        self.on_cancel = on_cancel or []
        self.on_finish = on_finish or []


class Operation:
    _calls_count: int = ScopedProperty(0)
    _current_operation: InnerOperation = ScopedProperty()

    def __init__(
        self,
        on_start: List[Callback] = None,
        on_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self._on_start = on_start or []
        self._on_complete = on_complete or []
        self._on_cancel = on_cancel or []
        self._on_finish = on_finish or []

    def _new_inner(self):
        return InnerOperation(
            on_start=self._on_start.copy(),
            on_complete=self._on_complete.copy(),
            on_cancel=self._on_cancel.copy(),
            on_finish=self._on_finish.copy(),
        )

    def __enter__(self):
        if self._calls_count == 0:
            self._start()

        self._calls_count += 1

    def __exit__(
        self, exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:

        self._calls_count -= 1

        if self._calls_count == 0:
            if exc_type is None:
                self._complete()
            else:
                self._cancel()

        return False

    @property
    def in_progress(self):
        return self._calls_count > 0

    def before_complete(self, callback: Callback):
        assert self.in_progress
        self._on_complete.insert(0, callback)

    def after_complete(self, callback: Callback):
        assert self.in_progress
        self._on_complete.append(callback)

    def on_cancel(self, callback: Callback):
        assert self.in_progress
        self._on_cancel.append(callback)

    def on_finish(self, callback: Callback):
        assert self.in_progress
        self._on_finish.append(callback)

    @staticmethod
    def _try_handle_all(callbacks: Iterable[Callback]):
        errors = []
        for callback in callbacks:
            try:
                callback()
            except Exception as exc:
                errors.append(exc)

        if errors:
            raise RuntimeError(errors)

    @staticmethod
    def _handle_for_first_error(callbacks: Iterable[Callback]):
        for callback in callbacks:
            callback()

    def _start(self):
        self._current_operation = self._new_inner()

        try:
            self._handle_for_first_error(
                self._current_operation.on_start
            )
        except Exception:
            self._cancel()
            self._finish()
            raise

    def _complete(self):
        try:
            self._handle_for_first_error(
                self._current_operation.on_complete
            )
        except Exception:
            self._cancel()
            raise
        finally:
            self._finish()

    def _cancel(self):
        self._try_handle_all(
            self._current_operation.on_cancel
        )

    def _finish(self):
        self._try_handle_all(
            self._current_operation.on_finish
        )
        self._current_operation = None
