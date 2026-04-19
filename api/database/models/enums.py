import enum


class UserType(enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class EnrollmentStatus(enum.Enum):
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    COMPLETED = "completed"


class SectionStatus(enum.Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TermType(enum.Enum):
    FALL = "fall"
    SPRING = "spring"
    SUMMER = "summer"


class EventRunStatus(enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EventSourceStatus(enum.Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventStatus(enum.Enum):
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    ASSIGNED = "assigned"


class EventTargetRole(enum.Enum):
    STUDENT = "student"
    STAFF = "staff"
    ADMIN = "admin"
    ALL = "all"


class EventAgent(enum.Enum):
    ORCHESTRATOR = "orchestrator"
    SEARCH = "search_agent"
    REASONING = "reasoning_agent"
    EVENT_CREATOR = "event_creator"


class EventCandidateDecision(enum.Enum):
    ACCEPT_PENDING = "accept_pending"
    ACCEPT_REVIEW = "accept_review"
    REJECT_QUALITY = "reject_quality"
    REJECT_DUPLICATE = "reject_duplicate"


class RuleMatchType(enum.Enum):
    SQL = "sql"           # has a clear, matchable condition — can be fired by query
    CONTEXTUAL = "contextual"  # ambiguous, needs reasoner to decide per student


class RuleStatus(enum.Enum):
    ACTIVE = "active"
    NEEDS_REVIEW = "needs_review"   # pass 2 flagged something wrong
    REJECTED = "rejected"           # pass 2 said remove it


class AssignmentStatus(enum.Enum):
    ACTIVE = "active"
    DISMISSED = "dismissed"
    ACTIONED = "actioned"


class AssignmentUrgency(enum.Enum):
    HIGH = "high"      # blocking=True
    MEDIUM = "medium"  # has deadline or consequence
    LOW = "low"        # informational

