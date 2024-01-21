from functools import wraps, partial
from typing import Any, Optional

from classic.components import add_extra_annotation
from classic.components.types import Method, Decorator

from .operation import Operation


def operation(
    original_method: Optional[Method] = None,
    prop_name: str = 'operation_',
) -> Method | Decorator:

    def decorate(function: Method) -> Method:

        @wraps(function)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            with getattr(self, prop_name):
                result = function(self, *args, **kwargs)

            return result

        return add_extra_annotation(wrapper, prop_name, Operation)

    if original_method:
        return decorate(original_method)

    return decorate


def customized_operation(prop_name: str):
    return partial(operation, prop_name=prop_name)
