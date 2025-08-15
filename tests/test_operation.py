from unittest.mock import Mock, call
from typing import ContextManager

import pytest

from classic.operations import Operation, operation, Cancel


class Service:

    def __init__(self, operation_: Operation):
        self.operation_ = operation_

    def work_with_context_manager(self):
        with self.operation_:
            return True

    @operation
    def work_with_decorator(self):
        return True

    @operation
    def just_fail(self):
        raise AssertionError

    def _add_callbacks(self, before, after, on_cancel, on_finish):
        self.operation_.before_complete(before)
        self.operation_.after_complete(after)
        self.operation_.on_cancel(on_cancel)
        self.operation_.on_finish(on_finish)

    @operation
    def success_with_callbacks(self, *args):
        self._add_callbacks(*args)
        return True

    @operation
    def failure_with_callbacks(self, *args):
        self._add_callbacks(*args)
        raise AssertionError

    @operation
    def success_with_nested_operation(self, *args):
        return self.success_with_callbacks(*args)

    def try_to_attach_callback_without_start(self, method_name):
        method = getattr(self.operation_, method_name)
        method(print)

    @operation
    def return_operation_in_progress_state(self):
        return self.operation_.in_progress

    def cancel_no_suppress(self):
        with self.operation_:
            raise self.operation_.Cancel

    def cancel_with_suppress(self):
        with self.operation_:
            raise Cancel(suppress=True)


class CM:
    def __init__(self):
        self.is_entered = False
        self.is_exited = False

    def __enter__(self):
        self.is_entered = True

    def __exit__(self, *args):
        self.is_exited = True
        return False


@pytest.fixture
def op():
    cm: ContextManager = Mock()
    cm.__enter__ = Mock()
    cm.__exit__ = Mock()

    return Operation(
        context_managers=[cm],
        before_start=[Mock()],
        after_start=[Mock()],
        before_complete=[Mock()],
        after_complete=[Mock()],
        on_cancel=[Mock()],
        on_finish=[Mock()],
    )


@pytest.fixture
def service(op):
    return Service(operation_=op)


@pytest.fixture
def callbacks():
    return [Mock(), Mock(), Mock(), Mock()]


def check_successful_call(operation_: Operation, times=1):
    calls = [call() for __ in range(times)]

    operation_._before_start[0].assert_has_calls(calls)

    cm = operation_._context_managers[0]
    cm.__enter__.assert_has_calls([
        call(cm) for __ in range(times)
    ])

    operation_._after_start[0].assert_has_calls(calls)

    operation_._before_complete[0].assert_has_calls(calls)

    cm.__exit__.assert_has_calls([
        call(cm, None, None, None) for __ in range(times)
    ])

    operation_._after_complete[0].assert_has_calls(calls)

    operation_._on_cancel[0].assert_not_called()

    operation_._on_finish[0].assert_has_calls(calls)


def check_failure_call(operation_: Operation, times=1):
    calls = [call() for __ in range(times)]

    operation_._before_start[0].assert_has_calls(calls)

    cm = operation_._context_managers[0]
    cm.__enter__.assert_has_calls([
        call(cm) for __ in range(times)
    ])

    operation_._after_start[0].assert_has_calls(calls)

    operation_._before_complete[0].assert_not_called()

    assert len(cm.__exit__.mock_calls) == times

    operation_._after_complete[0].assert_not_called()

    operation_._on_cancel[0].assert_has_calls(calls)

    operation_._on_finish[0].assert_has_calls(calls)


def test_operation_as_cm(service):
    result = service.work_with_context_manager()

    assert result is True
    check_successful_call(service.operation_)


def test_operation_as_decorator(service):
    result = service.work_with_decorator()

    assert result is True
    check_successful_call(service.operation_)


def test_operation_calls_callbacks_on_failure(service):
    with pytest.raises(AssertionError):
        service.just_fail()

    check_failure_call(service.operation_)


def test_dynamic_callback_on_success(service, callbacks):
    before, after, cancel, finish = callbacks

    result = service.success_with_callbacks(*callbacks)

    assert result is True
    check_successful_call(service.operation_)
    before.assert_called_once()
    after.assert_called_once()
    cancel.assert_not_called()
    finish.assert_called_once()


def test_dynamic_callback_on_failure(service, callbacks):
    before, after, cancel, finish = callbacks

    with pytest.raises(AssertionError):
        service.failure_with_callbacks(before, after, cancel, finish)

    check_failure_call(service.operation_)
    before.assert_not_called()
    after.assert_not_called()
    cancel.assert_called_once()
    finish.assert_called_once()


def test_nested_operation(service, callbacks):
    before, after, cancel, finish = callbacks

    result = service.success_with_nested_operation(
        before, after, cancel, finish,
    )

    assert result is True
    check_successful_call(service.operation_)
    before.assert_called_once()
    after.assert_called_once()
    cancel.assert_not_called()
    finish.assert_called_once()


def test_operation_is_reusable(service, callbacks):
    before, after, cancel, finish = callbacks

    result_1 = service.success_with_callbacks(before, after, cancel, finish)
    result_2 = service.success_with_callbacks(before, after, cancel, finish)

    assert result_1 is True
    assert result_2 is True
    check_successful_call(service.operation_, 2)
    before.assert_has_calls([call(), call()])
    after.assert_has_calls([call(), call()])
    cancel.assert_not_called()
    finish.assert_has_calls([call(), call()])


@pytest.mark.parametrize('method_name', [
    'before_complete',
    'after_complete',
    'on_cancel',
    'on_finish',
])
def test_dynamic_callbacks_works_only_after_start(service, method_name):
    with pytest.raises(AssertionError):
        service.try_to_attach_callback_without_start(method_name)


def test_in_progress_property(service):
    assert service.operation_.in_progress is False
    assert service.return_operation_in_progress_state() is True
    assert service.operation_.in_progress is False


def test_error_in_cm_enter(service, callbacks):
    before, after, cancel, finish = callbacks

    broken_cm = Mock()
    broken_cm.__enter__ = Mock(side_effect=AssertionError)
    broken_cm.__exit__ = Mock()

    service.operation_._context_managers = [broken_cm]

    with pytest.raises(AssertionError):
        service.success_with_callbacks(*callbacks)

    op = service.operation_
    op._before_start[0].assert_called_once()
    op._context_managers[0].__enter__.assert_called_once()
    op._after_start[0].assert_not_called()
    op._before_complete[0].assert_not_called()
    op._context_managers[0].__exit__.assert_not_called()
    op._after_complete[0].assert_not_called()
    op._on_cancel[0].assert_called_once()
    op._on_finish[0].assert_called_once()

    before.assert_not_called()
    after.assert_not_called()
    cancel.assert_not_called()
    finish.assert_not_called()


def test_error_in_before_start(service, callbacks):
    before, after, cancel, finish = callbacks

    service.operation_._before_start[0] = Mock(side_effect=AssertionError)

    with pytest.raises(AssertionError):
        service.success_with_callbacks(*callbacks)

    op = service.operation_
    op._before_start[0].assert_called_once()
    op._context_managers[0].__enter__.assert_not_called()
    op._after_start[0].assert_not_called()
    op._before_complete[0].assert_not_called()
    op._context_managers[0].__exit__.assert_not_called()
    op._after_complete[0].assert_not_called()
    op._on_cancel[0].assert_called_once()
    op._on_finish[0].assert_called_once()

    before.assert_not_called()
    after.assert_not_called()
    cancel.assert_not_called()
    finish.assert_not_called()


def test_error_in_after_start(service, callbacks):
    before, after, cancel, finish = callbacks

    service.operation_._after_start[0] = Mock(side_effect=AssertionError)

    with pytest.raises(AssertionError):
        service.success_with_callbacks(*callbacks)

    op = service.operation_
    op._before_start[0].assert_called_once()
    op._context_managers[0].__enter__.assert_called_once()
    op._after_start[0].assert_called_once()
    op._before_complete[0].assert_not_called()
    op._context_managers[0].__exit__.assert_called_once()
    op._after_complete[0].assert_not_called()
    op._on_cancel[0].assert_called_once()
    op._on_finish[0].assert_called_once()

    before.assert_not_called()
    after.assert_not_called()
    cancel.assert_not_called()
    finish.assert_not_called()


def test_error_in_before_complete(service, callbacks):
    before, after, cancel, finish = callbacks

    service.operation_._before_complete[0] = Mock(side_effect=AssertionError)

    with pytest.raises(AssertionError):
        service.success_with_callbacks(*callbacks)

    op = service.operation_
    op._before_start[0].assert_called_once()
    op._context_managers[0].__enter__.assert_called_once()
    op._after_start[0].assert_called_once()
    op._before_complete[0].assert_called_once()
    op._context_managers[0].__exit__.assert_called_once()
    op._after_complete[0].assert_not_called()
    op._on_cancel[0].assert_called_once()
    op._on_finish[0].assert_called_once()

    before.assert_not_called()
    after.assert_not_called()
    cancel.assert_called_once()
    finish.assert_called_once()


def test_error_in_cm_exit(service, callbacks):
    before, after, cancel, finish = callbacks

    broken_cm = Mock()
    broken_cm.__enter__ = Mock()
    broken_cm.__exit__ = Mock(side_effect=AssertionError)

    service.operation_._context_managers = [broken_cm]

    with pytest.raises(AssertionError):
        service.success_with_callbacks(*callbacks)

    op = service.operation_
    op._before_start[0].assert_called_once()
    op._context_managers[0].__enter__.assert_called_once()
    op._after_start[0].assert_called_once()
    op._before_complete[0].assert_called_once()
    op._context_managers[0].__exit__.assert_called_once()
    op._after_complete[0].assert_not_called()
    op._on_cancel[0].assert_called_once()
    op._on_finish[0].assert_called_once()

    before.assert_called_once()
    after.assert_not_called()
    cancel.assert_called_once()
    finish.assert_called_once()


def test_error_in_after_complete(service, callbacks):
    before, after, cancel, finish = callbacks

    service.operation_._after_complete[0] = Mock(side_effect=AssertionError)

    with pytest.raises(AssertionError):
        service.success_with_callbacks(*callbacks)

    op = service.operation_
    op._before_start[0].assert_called_once()
    op._context_managers[0].__enter__.assert_called_once()
    op._after_start[0].assert_called_once()
    op._before_complete[0].assert_called_once()
    op._context_managers[0].__exit__.assert_called_once()
    op._after_complete[0].assert_called_once()
    op._on_cancel[0].assert_called_once()
    op._on_finish[0].assert_called_once()

    before.assert_called_once()
    after.assert_not_called()
    cancel.assert_called_once()
    finish.assert_called_once()


def test_instancing_with_no_iterable():
    context_manager = Mock()
    before_start = Mock()
    after_start = Mock()
    before_complete = Mock()
    after_complete = Mock()

    operation_ = Operation(
        context_managers=context_manager,
        before_start=before_start,
        after_start=after_start,
        before_complete=before_complete,
        after_complete=[after_complete],
        on_cancel=None,
    )

    assert operation_._context_managers == [context_manager]
    assert operation_._before_start == [before_start]
    assert operation_._after_start == [after_start]
    assert operation_._before_complete == [before_complete]
    assert operation_._after_complete == [after_complete]
    assert operation_._on_cancel == []
    assert operation_._on_finish == []


def test_cancel_with_suppress_false(service):
    with pytest.raises(Cancel):
        service.cancel_no_suppress()


def test_cancel_with_suppress_true(service):
    service.cancel_with_suppress()
