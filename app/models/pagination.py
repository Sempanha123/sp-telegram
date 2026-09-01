from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass
class PaginationState:
    page: int = 1
    page_size: int = 100
    total_items: int = 0

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total_items / self.page_size))

    @property
    def offset(self) -> int:
        return max(0, (self.page - 1) * self.page_size)

    def clamp(self) -> None:
        self.page = max(1, min(self.page, self.total_pages))
