"""
audit.py — Audit trail and event log domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Optional

from supply_chain.models.common import EntityBase, require_nonempty, utc_now
from supply_chain.models.enums import EventType


@dataclass
class EventLog(EntityBase):
    """
    Append-only audit log entry preserving state changes and incident reports (NFR-07).
    PK: event_id (EVT-<6-digit>)
    Polymorphic reference: (entity_type, entity_id)
    """
    _pk_name: ClassVar[str] = "event_id"

    event_id:    str
    entity_type: str
    entity_id:   str
    event_type:  EventType
    old_status:  Optional[str] = None
    new_status:  Optional[str] = None
    detail:      str = ""
    created_at:  datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.event_id, "event_id")
        require_nonempty(self.entity_type, "entity_type")
        require_nonempty(self.entity_id, "entity_id")
        self._mark_initialized()
