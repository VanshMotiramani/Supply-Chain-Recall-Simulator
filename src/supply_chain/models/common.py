"""
common.py — Base entity classes and shared validation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import ClassVar, Optional, Sequence


def utc_now() -> datetime:
    """Return current UTC timestamp without deprecation warnings."""
    return datetime.now(timezone.utc)


@dataclass
class EntityBase:
    """
    Base class for all domain entities.
    Enforces runtime immutability on primary key fields once instantiated.
    """
    _pk_name: ClassVar[str] = ""

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_initialized", False) and name == self._pk_name:
            raise AttributeError(
                f"Cannot mutate immutable primary key '{name}' on {self.__class__.__name__}"
            )
        super().__setattr__(name, value)

    def _mark_initialized(self) -> None:
        """Call at the end of __post_init__ to lock the primary key."""
        object.__setattr__(self, "_initialized", True)


def require_nonempty(value: str, field_name: str) -> None:
    """Raise ValueError if value is empty or pure whitespace."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def require_positive(value: int, field_name: str) -> None:
    """Raise ValueError if value is not an integer > 0."""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be > 0, got {value}")


def require_non_negative(value: int, field_name: str) -> None:
    """Raise ValueError if value is not an integer >= 0."""
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be >= 0, got {value}")


def require_date_order(
    start: date,
    end: Optional[date],
    start_name: str = "effective_start",
    end_name: str = "effective_end",
) -> None:
    """Raise ValueError if end date precedes start date."""
    if end is not None and end < start:
        raise ValueError(f"{end_name} ({end}) must be >= {start_name} ({start})")


def freeze_string_tuple(items: Sequence[str], field_name: str) -> tuple[str, ...]:
    """Validate and convert a sequence of strings into an immutable tuple."""
    if not items:
        raise ValueError(f"{field_name} must contain at least one entry")
    result: list[str] = []
    for idx, item in enumerate(items):
        require_nonempty(item, f"{field_name}[{idx}]")
        result.append(item.strip())
    return tuple(result)
