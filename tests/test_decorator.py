from unittest.mock import Mock

from classic.operations import Operation, operation


class SomeService:

    def __init__(self, read: Operation):
        self.read = read

    @operation('read')
    def some_method(self):
        pass


def test_operation_customize():

    class CM:

        def __init__(self):
            self.mock = Mock()
            self.mock.__enter__ = Mock()
            self.mock.__exit__ = Mock()

        def __enter__(self):
            self.mock.__enter__(self)

        def __exit__(self, *args):
            self.mock.__exit__(self, *args)

    cm = CM()
    op = Operation(context_managers=cm)
    service = SomeService(read=op)

    service.some_method()

    cm.mock.__enter__.assert_called_once()
    cm.mock.__exit__.assert_called_once()
