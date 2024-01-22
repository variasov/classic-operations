from contextlib import ExitStack
from types import TracebackType
from typing import List, Optional, Type, Iterable, ContextManager
import threading

from .callbacks import Callback, Callbacks


class Operation(threading.local):
    """
    Класс для выделения границ операций в приложении.


    """

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
        self._calls_count = 0
        self._exit_stack = ExitStack()
        self._current = None

    def _new_callbacks(self):
        """Порождает новый контейнер с callback-ами."""
        return Callbacks(
            before_complete=self._before_complete.copy(),
            after_complete=self._after_complete.copy(),
            on_cancel=self._on_cancel.copy(),
            on_finish=self._on_finish.copy(),
        )

    def __enter__(self):
        """
        Запуск операции.
        При первом обращении запускает callback-и before_start, затем
        выполняет вход во все указанные контекстные менеджеры, затем
        запускает callback-и after_start.
        """
        if self._calls_count == 0:
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
                except Exception as exc_:
                    new_exc = exc_
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
        """

        """
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
    def in_progress(self) -> bool:
        """Сигнализирует о состоянии операции.
        True - запущена, False - не запущена.
        """
        return self._calls_count > 0

    def before_complete(self, callback: Callback):
        """Добавляет callback для вызова перед успешным завершением операции.
        Callback может быть любым вызываемым объектом
        и не должен принимать аргументов.
        """
        assert self.in_progress
        self._current.before_complete.append(callback)

    def after_complete(self, callback: Callback):
        """Добавляет callback для вызова после успешного завершения операции.
        Callback может быть любым вызываемым объектом
        и не должен принимать аргументов.
        """
        assert self.in_progress
        self._current.after_complete.append(callback)

    def on_cancel(self, callback: Callback):
        """Добавляет callback для вызова при отмене операции.
        Callback может быть любым вызываемым объектом
        и не должен принимать аргументов.
        """
        assert self.in_progress
        self._current.on_cancel.append(callback)

    def on_finish(self, callback: Callback):
        """Добавляет callback для вызова после окончания операции.
        Callback может быть любым вызываемым объектом
        и не должен принимать аргументов.
        """
        assert self.in_progress
        self._current.on_finish.append(callback)

    @staticmethod
    def _try_handle_all(callbacks: Iterable[Callback]):
        """Вызывает указанные callbacks последовательно,
        отлавливая и аккумулируя ошибки из callbacks.
        В случае, если ошибки все же произошли, выкинет RuntimeError,
        содержащий список ошибок.
        """
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
        """Попытка вызывать указанные callbacks последовательно,
        без отлова ошибок в callbacks.
        """
        for callback in callbacks:
            callback()

    def _cancel(self):
        """Отмена операции.
        Вызывает все callbacks, назначенные на отмену операции,
        независимо друг от друга.
        """
        self._try_handle_all(
            self._current.on_cancel
        )

    def _finish(self):
        """Завершение операции.
        Вызывает все callbacks, назначенные на завершение операции,
        чистит текущее состояние.
        """
        self._try_handle_all(
            self._current.on_finish
        )
        del self._current
