from functools import wraps

from classic.components import add_extra_annotation, doublewrap

from .operation import Operation, Cancel


@doublewrap
def operation(method, prop: str = 'operation_', type_: Operation = Operation):
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

    return add_extra_annotation(wrapper, prop, type_)


operation.Cancel = Cancel
