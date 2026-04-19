from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base
from .enums import (
    AssignmentStatus,
    AssignmentUrgency,
    EventAgent,
    EventCandidateDecision,
    EventRunStatus,
    EventSourceStatus,
    EventStatus,
    EventTargetRole,
    RuleMatchType,
    RuleStatus,
)


class EventRun(Base):
    __tablename__ = "event_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    status = Column(SQLEnum(EventRunStatus, validate_strings=True), nullable=False, default=EventRunStatus.RUNNING)
    started_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    completed_at = Column(TIMESTAMP)
    last_category = Column(Text)
    chunks_processed = Column(Integer, default=0, nullable=False)
    sources_processed = Column(Integer, default=0, nullable=False)
    events_created = Column(Integer, default=0, nullable=False)
    error_message = Column(Text)

    source_logs = relationship("EventSourceLog", back_populates="run")
    events = relationship("Event", back_populates="run")
    agent_logs = relationship("EventAgentLog", back_populates="run")
    candidate_logs = relationship("EventCandidateLog", back_populates="run")


class EventSourceLog(Base):
    __tablename__ = "event_source_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id = Column(UUID(as_uuid=True), ForeignKey("event_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_key = Column(String(64), nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    parent_category = Column(Text, nullable=False)
    status = Column(SQLEnum(EventSourceStatus, validate_strings=True), nullable=False, default=EventSourceStatus.PENDING)
    reason = Column(Text)
    chunk_count = Column(Integer, default=0, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    completed_at = Column(TIMESTAMP)

    run = relationship("EventRun", back_populates="source_logs")

    __table_args__ = (
        UniqueConstraint("run_id", "source_key", name="uq_event_source_log_run_source"),
    )


class EventSourceCheckpoint(Base):
    __tablename__ = "event_source_checkpoints"

    source_key = Column(String(64), primary_key=True)
    source_url = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    parent_category = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    last_run_id = Column(UUID(as_uuid=True), ForeignKey("event_runs.id", ondelete="SET NULL"))
    last_processed_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_url", "content_hash", name="uq_event_checkpoint_source_content"),
    )


class Event(Base):
    __tablename__ = "regulatory_events"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id = Column(UUID(as_uuid=True), ForeignKey("event_runs.id", ondelete="SET NULL"), index=True)
    source_key = Column(String(64), nullable=False, index=True)
    source_chunk_ids = Column(JSONB, nullable=False, default=list)
    source_url = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    parent_category = Column(Text, nullable=False)
    obligation_text = Column(Text, nullable=False)
    evidence_excerpt = Column(Text, nullable=False)
    target_role = Column(SQLEnum(EventTargetRole, validate_strings=True), nullable=False)
    status = Column(SQLEnum(EventStatus, validate_strings=True), nullable=False, default=EventStatus.PENDING)
    fingerprint = Column(String(64), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    run = relationship("EventRun", back_populates="events")


class EventAgentLog(Base):
    __tablename__ = "event_agent_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id = Column(UUID(as_uuid=True), ForeignKey("event_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_key = Column(String(64), index=True)
    agent = Column(SQLEnum(EventAgent, validate_strings=True), nullable=False)
    state = Column(String(64), nullable=False)
    decision = Column(String(64), nullable=False)
    reason = Column(Text)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    run = relationship("EventRun", back_populates="agent_logs")


class EventCandidateLog(Base):
    __tablename__ = "event_candidate_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id = Column(UUID(as_uuid=True), ForeignKey("event_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_key = Column(String(64), index=True)
    source_url = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    parent_category = Column(Text, nullable=False)
    target_role = Column(Text, nullable=False)
    candidate_hash = Column(String(64), nullable=False, index=True)
    candidate_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)
    decision = Column(SQLEnum(EventCandidateDecision, validate_strings=True), nullable=False)
    reason_code = Column(String(64), nullable=False)
    metrics = Column(JSONB, nullable=False, default=dict)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    run = relationship("EventRun", back_populates="candidate_logs")


class RegulationRule(Base):
    """One extracted action object from a regulation document.

    Populated by the LLM extraction pipeline (events/orchestrator.py).
    Two types:
      - sql:         action trigger is concrete enough to match students via query
      - contextual:  ambiguous, needs the reasoner to decide per-student at runtime
    """
    __tablename__ = "regulation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id = Column(UUID(as_uuid=True), ForeignKey("event_runs.id", ondelete="SET NULL"), index=True)

    # Source traceability — every rule points back to exact KB chunks
    source_doc_url = Column(Text, nullable=False)
    source_chunk_ids = Column(JSONB, nullable=False, default=list)  # list of KB UUIDs
    evidence_quote = Column(Text, nullable=False)  # exact quote from document that backs this rule

    # The action itself — written in plain user-facing language
    rule_text = Column(Text, nullable=False)
    applies_to = Column(Text, nullable=False)       # e.g. "undergraduate students"
    trigger = Column(Text)                           # e.g. "when GPA is below 1.80 during registration"
    deadline = Column(Text)                          # e.g. "within 2 weeks of grade release"
    valid_from = Column(Date)                        # explicit date only when the source gives one
    valid_until = Column(Date)                       # explicit date only when the source gives one
    blocking = Column(Boolean, nullable=False, default=False)  # whether the action blocks progress if ignored
    consequence = Column(Text)                       # what happens if the action is ignored / unmet
    authority = Column(Text)                         # e.g. "faculty board"
    exceptions = Column(Text)                        # e.g. "exempt if enrolled before 2020"
    target_role = Column(SQLEnum(EventTargetRole, validate_strings=True), nullable=False)

    # Matching strategy
    match_type = Column(SQLEnum(RuleMatchType, validate_strings=True), nullable=False)
    sql_condition = Column(Text)  # filled only when match_type=sql, e.g. "gpa < 1.80"

    # Quality
    status = Column(SQLEnum(RuleStatus, validate_strings=True), nullable=False, default=RuleStatus.ACTIVE)
    pass2_notes = Column(Text)        # reviewer comments from pass 2
    confidence = Column(Text)         # "explicit" | "inferred" | "ambiguous"

    # Dedup
    fingerprint = Column(String(64), nullable=False, unique=True)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


class UserRuleAssignment(Base):
    """A regulation rule assigned to a user (any role) by the user agent.

    Created automatically when the agent determines a rule applies to a user.
    Deduplicated by (user_id, rule_id) — re-runs update reason/urgency in place.
    """
    __tablename__ = "user_rule_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("regulation_rules.id", ondelete="CASCADE"), nullable=False, index=True)

    match_type = Column(SQLEnum(RuleMatchType, validate_strings=True), nullable=False)
    urgency = Column(SQLEnum(AssignmentUrgency, validate_strings=True), nullable=False, default=AssignmentUrgency.LOW)
    status = Column(SQLEnum(AssignmentStatus, validate_strings=True), nullable=False, default=AssignmentStatus.ACTIVE)

    reason = Column(Text, nullable=False)

    assigned_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    rule = relationship("RegulationRule")

    __table_args__ = (
        UniqueConstraint("user_id", "rule_id", name="uq_user_rule_assignment"),
    )
