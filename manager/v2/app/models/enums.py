"""Central status values for accounts and jobs."""

from enum import Enum


class AccountStatus(str, Enum):
    NEVER_RUN = "never_run"
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    PAUSED = "paused"
    SESSION_VALID = "session_valid"
    SESSION_REFRESHED = "session_refreshed"
    PROFILE_BUSY = "profile_busy"
    MANUAL_VERIFICATION_REQUIRED = "manual_verification_required"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"
