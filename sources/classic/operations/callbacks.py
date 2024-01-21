from typing import Callable, List


Callback = Callable[[], None]


class Callbacks:

    def __init__(
        self,
        before_complete: List[Callback] = None,
        after_complete: List[Callback] = None,
        on_cancel: List[Callback] = None,
        on_finish: List[Callback] = None,
    ):
        self.before_complete = before_complete or []
        self.after_complete = after_complete or []
        self.on_cancel = on_cancel or []
        self.on_finish = on_finish or []
