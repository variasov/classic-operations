import threading


class Counter:

    def __init__(self):
        self._calls_count = 0

    def increment(self):
        self._calls_count += 1

    def decrement(self):
        if self._calls_count > 0:
            self._calls_count -= 1

    def reset(self):
        self._calls_count = 0

    @property
    def is_zero(self):
        return self._calls_count == 0

    @property
    def value(self):
        return self._calls_count


class ThreadSafeCounter(Counter, threading.local):
    pass
