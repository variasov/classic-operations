import threading
from typing import Any
from weakref import ref


def get_or_create_local_dict():
    thread = threading.current_thread()

    storage = getattr(thread, '__storage__', None)
    if storage is None:
        storage = {}
        setattr(thread, '__storage__', storage)

    return storage


class LocalStorage:
    _owner_id: int

    @property
    def local(self):
        return get_or_create_local_dict()

    def __getitem__(self, item):
        return self.local[item]

    def __setitem__(self, key, value):
        self.local[key] = value

    def __delitem__(self, item):
        del self.local[item]


class ScopedProperty:

    def __init__(self, default: Any = None):
        self.default = default

    def __get__(self, instance, owner):
        dct = get_or_create_local_dict()
        value = dct.get((id(self), id(instance)), None)
        if value is None:
            return self.default
        return value[0]

    def __set__(self, instance, value):
        dct = get_or_create_local_dict()

        def instance_deleted():
            try:
                del dct[id(self), id(instance)]
            except KeyError:
                pass

        ref(instance, instance_deleted)
        dct[id(self), id(instance)] = value, ref

    def __delete__(self, instance):
        dct = get_or_create_local_dict()
        try:
            del dct[id(self), id(instance)]
        except KeyError:
            pass
