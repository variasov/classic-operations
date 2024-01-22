from functools import wraps

try:
    from classic.components import add_extra_annotation
except ImportError:
    def add_extra_annotation(fn):
        return fn

from .operation import Operation


def doublewrap(f):
    """
    Классный сниппет, облегчающий создание декораторов с параметрами.
    Взято отсюда: https://stackoverflow.com/a/14412901
    """

    @wraps(f)
    def new_dec(*args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            # actual decorated function
            return f(args[0])
        else:
            # decorator arguments
            return lambda realf: f(realf, *args, **kwargs)

    return new_dec


@doublewrap
def operation(method, prop: str = 'operation_'):
    """Сахар для облегчения применения операций.
    По сути просто оборачивает функцию в блок with c указанным полем из self.

    Если установлена библиотека classic.components, то добавляет операцию в
    дополнительные аннотации.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with getattr(self, prop):
            result = method(self, *args, **kwargs)

        return result

    return add_extra_annotation(wrapper, prop, Operation)
