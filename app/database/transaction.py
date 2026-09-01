from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def transaction_scope(database) -> Iterator[object]:
    """Compatibility helper for code that prefers a standalone transaction function."""
    with database.transaction() as connection:
        yield connection
