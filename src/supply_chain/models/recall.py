"""
recall.py — Recall simulation domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar, Optional

from supply_chain.models.common import (
    EntityBase,
    require_date_order,
    require_nonempty,
    utc_now,
)
from supply_chain.models.enums import (
    NotificationChannel,
    RecallActionStatus,
    RecallActionType,
    RecallCaseStatus,
    RecallDisposition,
    RecallTriggerEntityType,
)


@dataclass
class RecallCase(EntityBase):
    """
    Quality or safety recall incident header.
    PK: recall_id (REC-2026-<6-digit>)
    FK: trigger_entity_id -> MaterialLot.lot_id or FinishedLot.fin_lot_id
    """
    _pk_name: ClassVar[str] = "recall_id"

    recall_id:           str
    trigger_entity_type: RecallTriggerEntityType
    trigger_entity_id:   str
    reason:              str
    status:              RecallCaseStatus
    opened_date:         date
    closed_date:         Optional[date] = None
    created_at:          datetime = field(default_factory=utc_now)
    updated_at:          datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.recall_id, "recall_id")
        require_nonempty(self.trigger_entity_id, "trigger_entity_id")
        require_nonempty(self.reason, "reason")
        require_date_order(self.opened_date, self.closed_date, "opened_date", "closed_date")
        self._mark_initialized()


@dataclass
class RecallAction(EntityBase):
    """
    Specific downstream recall action targeted at an affected delivery.
    PK: action_id (RACT-2026-<6-digit>)
    FK: recall_id -> RecallCase.recall_id, delivery_id -> Delivery.delivery_id
    """
    _pk_name: ClassVar[str] = "action_id"

    action_id:               str
    recall_id:               str
    delivery_id:             str
    action_type:             RecallActionType
    notification_channel:    NotificationChannel
    status:                  RecallActionStatus
    notified_at:             Optional[datetime] = None
    quarantine_requested_at: Optional[datetime] = None
    recovered_at:            Optional[datetime] = None
    disposition:             Optional[RecallDisposition] = None
    completed_at:            Optional[datetime] = None
    created_at:              datetime = field(default_factory=utc_now)
    updated_at:              datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.action_id, "action_id")
        require_nonempty(self.recall_id, "recall_id")
        require_nonempty(self.delivery_id, "delivery_id")
        self._mark_initialized()
