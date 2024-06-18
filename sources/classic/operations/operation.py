from contextlib import ExitStack
from types import TracebackType
from typing import (
    List, Optional, Type, Iterable, ContextManager, Union, ClassVar
)
import threading

from .callbacks import Callback, Callbacks


OptionalContextManagers = Union[ContextManager, List[ContextManager], None]
OptionalCallbacks = Union[Callback, List[Callback], None]


def to_list(obj):
    if obj is None:
        return []
    elif isinstance(obj, Iterable):
        return list(obj)
    else:
        return [obj]


class Cancel(Exception):

    def __init__(self, suppress: bool = False):
        self.suppress = suppress


class Operation(threading.local):
    """
    Класс для выделения границ операций в приложении.

    Представляет собой контекстный менеджер, которым следует оборачивать
    действия пользователей в приложении. На границах операции, то есть входе и
    выходе в блок with, происходит вызов коллбеков и работа с вложенными
    контекстными менеджерами. Подробно жизненный цикл описан в README и
    docstring-ах методов.

    Потокобезопасен, локален для текущего потока.
    """

    _context_managers: List[ContextManager]
    _before_start: List[Callback]
    _after_start: List[Callback]
    _before_complete: List[Callback]
    _after_complete: List[Callback]
    _on_cancel: List[Callback]
    _on_finish: List[Callback]
    _exit_stack: ExitStack
    _calls_count: int
    _current: Optional[Callbacks]

    Cancel: ClassVar[Type[Cancel]] = Cancel

    def __init__(
        self,
        context_managers: OptionalContextManagers = None,
        before_start: OptionalCallbacks = None,
        after_start: OptionalCallbacks = None,
        before_complete: OptionalCallbacks = None,
        after_complete: OptionalCallbacks = None,
        on_cancel: OptionalCallbacks = None,
        on_finish: OptionalCallbacks = None,
    ):
        self._context_managers = to_list(context_managers)
        self._before_start = to_list(before_start)
        self._after_start = to_list(after_start)
        self._before_complete = to_list(before_complete)
        self._after_complete = to_list(after_complete)
        self._on_cancel = to_list(on_cancel)
        self._on_finish = to_list(on_finish)
        self._exit_stack = ExitStack()
        self._calls_count = 0
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

        При первом обращении запускает коллбеки before_start, затем
        выполняет вход во все указанные контекстные менеджеры, затем
        запускает коллбеки after_start.

        Если что-то пошло не так, вызовет on_cancel, затем on_finish, выбросит
        исключение наружу.
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
        Окончание операции.

        Вызывает коллбеки before_complete, потом совершает выход из контекстных
        менеджеров, затем вызывает after_complete.

        Если что-то пошло не так, вызовет on_cancel, затем on_finish, выбросит
        исключение наружу.
        """
        self._calls_count -= 1

        if self._calls_count != 0:
            return False

        suppress = False

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
                # Используется raise для того, чтобы в случае исключения в
                # callback отработал _cancel()
                raise exc_val
        except Exception:
            self._cancel()
            raise
        finally:
            self._finish()
            if isinstance(exc_val, Cancel):
                return exc_val.suppress

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
