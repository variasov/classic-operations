from contextlib import ExitStack
from types import TracebackType
from typing import Callable, List, Optional, Type, Iterable, ContextManager

from .local_dict import ScopedProperty


Callback = Callable[[], None]


class Callbacks:

    def __init__(
        self,
        before_complete: List[Callback] = None,
        after_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self.before_complete = before_complete or []
        self.after_complete = after_complete or []
        self.on_cancel = on_cancel or []
        self.on_finish = on_finish or []


class Operation:
    _calls_count: int = ScopedProperty(0)
    _current: Callbacks = ScopedProperty()
    _exit_stack = ScopedProperty()

    def __init__(
        self,
        context_managers: List[ContextManager] = None,
        on_start: List[Callback] = None,
        before_complete: List[Callback] = None,
        after_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self.context_managers = context_managers or []
        self._on_start = on_start or []
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

            try:
                for context in self.context_managers:
                    self._exit_stack.enter_context(context)

                self._handle_for_first_error(self._on_start)
            except Exception:
                self._exit_stack.pop_all()
                self._cancel()
                self._finish()
                raise

            self._current = self._new_callbacks()

        self._calls_count += 1

    def __exit__(
        self, exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:

        self._calls_count -= 1

        if self._calls_count != 0:
            return False

        try:
            if exc_type is None:
                self._handle_for_first_error(
                    self._current.before_complete
                )

            self._exit_stack.__exit__(exc_type, exc_val, exc_tb)

            if exc_type is None:
                self._handle_for_first_error(
                    self._current.after_complete
                )
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
        self._current.before_complete.insert(0, callback)

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
