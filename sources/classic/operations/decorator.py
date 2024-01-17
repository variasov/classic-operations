from functools import wraps
from typing import Any, Optional

from classic.components import add_extra_annotation
from classic.components.types import Method, Decorator

from .operation import NewOperation


def operation(
    original_method: Optional[Method] = None,
    prop_name: str = 'new_operation',
) -> Method | Decorator:

    def decorate(function: Method) -> Method:

        @wraps(function)
        def wrapper(obj, *args: Any, **kwargs: Any) -> Any:
            with getattr(obj, prop_name)():
                result = function(obj, *args, **kwargs)

            return result

        return add_extra_annotation(wrapper, prop_name, NewOperation)

    if original_method:
        return decorate(original_method)

    return decorate
