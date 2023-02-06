from functools import wraps
from typing import Any

from classic.components import add_self_annotation

from .operation import NewOperation


def operation(
    original_method=None,
    prop_name: str = 'new_operation',
    **params: Any,
):

    def decorate(function):

        @wraps(function)
        def wrapper(obj, *args: Any, **kwargs: Any) -> Any:
            with getattr(obj, prop_name)(**params):
                result = function(obj, *args, **kwargs)

            return result

        wrapper = add_self_annotation(wrapper, prop_name, NewOperation)

        return wrapper

    if original_method:
        return decorate(original_method)

    return decorate
