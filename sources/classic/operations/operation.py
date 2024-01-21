from contextlib import ExitStack
from types import TracebackType
from typing import List, Optional, Type, Iterable, ContextManager

from classic.thread_safety_utils import ScopedProperty

from .callbacks import Callback, Callbacks


class Operation:
    _calls_count: int = ScopedProperty(0)
    _current: Callbacks = ScopedProperty()
    _exit_stack = ScopedProperty()

    def __init__(
        self,
        context_managers: List[ContextManager] = None,
        before_start: List[Callback] = None,
        after_start: List[Callback] = None,
        before_complete: List[Callback] = None,
        after_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self._context_managers = context_managers or []
        self._before_start = before_start or []
        self._after_start = after_start or []
        self._before_complete = before_complete or []
        self._after_complete = after_complete or []
        self._on_cancel = on_cancel or []
        self._on_finish = on_finish or []

    def _new_callbacks(self):
        return Callbacks(
            before_complete=self._before_complete.copy(),
            after_complete=self._after_complete.copy(),
            on_cancel=self._on_cancel.copy(),
            on_finish=self._on_finish.copy(),
        )

    def __enter__(self):
        if self._calls_count == 0:
            self._exit_stack = ExitStack()
            self._current = self._new_callbacks()

            try:
                self._handle_for_first_error(self._before_start)

                self._exit_stack.__enter__()
                for context in self._context_managers:
                    self._exit_stack.enter_context(context)

                self._handle_for_first_error(self._after_start)
            except Exception as exc:
                new_exc = None
                try:
                    self._exit_stack.__exit__(type(exc), exc, exc.__traceback__)
                except Exception as new_exc:
                    pass
                try:
                    self._cancel()
                finally:
                    self._finish()
                raise new_exc or exc

        self._calls_count += 1

    def __exit__(
        self, exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:

        self._calls_count -= 1

        if self._calls_count != 0:
            return False

        if exc_type is None:
            try:
                self._handle_for_first_error(
                    self._current.before_complete
                )
            except Exception as exc:
                exc_type = type(exc)
                exc_val = exc
                exc_tb = exc.__traceback__

        try:
            self._exit_stack.__exit__(exc_type, exc_val, exc_tb)
        except Exception as exc:
            exc_type = type(exc)
            exc_val = exc

        try:
            if exc_type is None:
                self._handle_for_first_error(
                    self._current.after_complete
                )
            else:
                raise exc_val
        except Exception:
            self._cancel()
            raise
        finally:
            self._finish()

        return False

    @property
    def in_progress(self):
        return self._calls_count > 0

    def before_complete(self, callback: Callback):
        assert self.in_progress
        self._current.before_complete.append(callback)

    def after_complete(self, callback: Callback):
        assert self.in_progress
        self._current.after_complete.append(callback)

    def on_cancel(self, callback: Callback):
        assert self.in_progress
        self._current.on_cancel.append(callback)

    def on_finish(self, callback: Callback):
        assert self.in_progress
        self._current.on_finish.append(callback)

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

    def _cancel(self):
        self._try_handle_all(
            self._current.on_cancel
        )

    def _finish(self):
        self._try_handle_all(
            self._current.on_finish
        )
        del self._current
