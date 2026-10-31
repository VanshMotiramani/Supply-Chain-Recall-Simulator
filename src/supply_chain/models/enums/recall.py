"""
Recall simulation enums.
"""

from enum import StrEnum


class RecallCaseStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class RecallActionStatus(StrEnum):
    NOTIFIED = "NOTIFIED"
    QUARANTINE_REQUESTED = "QUARANTINE_REQUESTED"
    RECOVERED = "RECOVERED"
    DISPOSED = "DISPOSED"
    RELEASED = "RELEASED"
    COMPLETED = "COMPLETED"


class RecallActionType(StrEnum):
    NOTIFY = "NOTIFY"
    QUARANTINE = "QUARANTINE"
    RECOVER = "RECOVER"
    DISPOSE = "DISPOSE"
    RELEASE = "RELEASE"


class RecallDisposition(StrEnum):
    DISPOSED = "DISPOSED"
    RELEASED = "RELEASED"


class NotificationChannel(StrEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    EDI = "EDI"
    PORTAL = "PORTAL"


class RecallTriggerEntityType(StrEnum):
    MATERIAL_LOT = "MATERIAL_LOT"
    FINISHED_LOT = "FINISHED_LOT"
