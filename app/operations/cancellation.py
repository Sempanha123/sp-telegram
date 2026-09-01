from __future__ import annotations

import threading


class CancellationToken:
    """Cooperative cancellation token; never force-terminates worker threads."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise OperationCancelled("Operation cancelled safely.")


class OperationCancelled(RuntimeError):
    pass
