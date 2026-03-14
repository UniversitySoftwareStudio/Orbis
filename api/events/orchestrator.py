from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.logging import get_logger
from database.models import (
    EventAgent,
    EventAgentLog,
    EventRun,
    EventRunStatus,
    EventSourceCheckpoint,
    EventSourceLog,
    EventSourceStatus,
)
from events.event_creator import EventCreator
from events.reasoning_agent import ReasoningAgent
from events.search_agent import SearchAgent

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    run_id: str
    status: str
    sources_processed: int
    chunks_processed: int
    events_created: int


class EventPipelineOrchestrator:
    """State owner. Workers stay stateless."""

    def __init__(self, search_agent: SearchAgent | None = None, reasoning_agent: ReasoningAgent | None = None, event_creator: EventCreator | None = None) -> None:
        self.search_agent = search_agent or SearchAgent()
        self.reasoning_agent = reasoning_agent or ReasoningAgent()
        self.event_creator = event_creator or EventCreator()

    def start_run(self, db: Session) -> EventRun:
        run = EventRun(status=EventRunStatus.RUNNING)
        db.add(run)
        db.commit()
        db.refresh(run)
        self._emit_agent_log(
            db=db,
            run_id=run.id,
            source_key=None,
            agent=EventAgent.ORCHESTRATOR,
            state="IDLE",
            decision="run_started",
            reason="new_run_created",
            payload={"run_id": str(run.id)},
        )
        db.commit()
        return run

    def run_existing(self, db: Session, run: EventRun) -> PipelineResult:
        in_memory_seen: set[str] = set()
        chunks_processed = 0
        sources_processed = 0
        events_created = 0

        try:
            sources = self.search_agent.fetch_regulation_sources(db)
            processable_sources = sum(1 for source in sources if source.should_process)
            self._emit_agent_log(
                db=db,
                run_id=run.id,
                source_key=None,
                agent=EventAgent.SEARCH,
                state="PLANNING",
                decision="sources_loaded",
                reason="regulation_tree_loaded",
                payload={"source_count": len(sources), "processable_sources": processable_sources},
            )
            db.commit()
            for source in sources:
                if source.source_key in in_memory_seen:
                    self._log_source(db, run.id, source, EventSourceStatus.SKIPPED, "seen_in_memory")
                    self._emit_agent_log(
                        db=db,
                        run_id=run.id,
                        source_key=source.source_key,
                        agent=EventAgent.SEARCH,
                        state="FILTER",
                        decision="skip",
                        reason="seen_in_memory",
                        payload={"url": source.canonical_url, "category": source.category},
                    )
                    continue
                in_memory_seen.add(source.source_key)

                if not source.should_process:
                    skip_reason = source.skip_reason or "skip_source"
                    self._log_source(db, run.id, source, EventSourceStatus.SKIPPED, skip_reason)
                    self._emit_agent_log(
                        db=db,
                        run_id=run.id,
                        source_key=source.source_key,
                        agent=EventAgent.SEARCH,
                        state="FILTER",
                        decision="skip",
                        reason=skip_reason,
                        payload={
                            "url": source.canonical_url,
                            "category": source.category,
                            "signal_score": source.regulatory_signal_score,
                        },
                    )
                    db.commit()
                    continue

                checkpoint = db.get(EventSourceCheckpoint, source.source_key)
                if checkpoint is not None:
                    self._log_source(db, run.id, source, EventSourceStatus.SKIPPED, "checkpoint_exists")
                    self._emit_agent_log(
                        db=db,
                        run_id=run.id,
                        source_key=source.source_key,
                        agent=EventAgent.SEARCH,
                        state="FILTER",
                        decision="skip",
                        reason="checkpoint_exists",
                        payload={"url": source.canonical_url, "category": source.category},
                    )
                    continue

                self._log_source(db, run.id, source, EventSourceStatus.PENDING, "processing")
                self._emit_agent_log(
                    db=db,
                    run_id=run.id,
                    source_key=source.source_key,
                    agent=EventAgent.ORCHESTRATOR,
                    state="PROCESSING_SOURCE",
                    decision="start",
                    reason="source_selected",
                    payload={
                        "url": source.canonical_url,
                        "category": source.category,
                        "parent_category": source.parent_category,
                        "chunk_count": source.chunk_count,
                    },
                )
                candidates = self.reasoning_agent.extract(source)
                self._emit_agent_log(
                    db=db,
                    run_id=run.id,
                    source_key=source.source_key,
                    agent=EventAgent.REASONING,
                    state="EXTRACT",
                    decision="obligations_extracted",
                    reason="deterministic_sentence_scan",
                    payload={"candidate_count": len(candidates)},
                )
                persist_stats = self.event_creator.persist_candidates(db, run.id, candidates)
                self._emit_agent_log(
                    db=db,
                    run_id=run.id,
                    source_key=source.source_key,
                    agent=EventAgent.EVENT_CREATOR,
                    state="PERSIST",
                    decision="persist_summary",
                    reason="deterministic_validation_and_dedup",
                    payload={
                        "created": persist_stats.created,
                        "created_pending": persist_stats.created_pending,
                        "created_review": persist_stats.created_review,
                        "skipped_quality": persist_stats.skipped_quality,
                        "skipped_duplicate": persist_stats.skipped_duplicate,
                        "reviewed_by_llm": persist_stats.reviewed_by_llm,
                        "rejection_reasons": persist_stats.rejection_reasons,
                    },
                )

                db.add(
                    EventSourceCheckpoint(
                        source_key=source.source_key,
                        source_url=source.canonical_url,
                        category=source.category,
                        parent_category=source.parent_category,
                        content_hash=source.content_hash,
                        last_run_id=run.id,
                    )
                )

                self._log_source(db, run.id, source, EventSourceStatus.DONE, f"events_created={persist_stats.created}")
                chunks_processed += source.chunk_count
                sources_processed += 1
                events_created += persist_stats.created

                run.last_category = source.category
                run.chunks_processed = chunks_processed
                run.sources_processed = sources_processed
                run.events_created = events_created
                db.commit()

            run.status = EventRunStatus.COMPLETED
            run.completed_at = func.now()
            run.chunks_processed = chunks_processed
            run.sources_processed = sources_processed
            run.events_created = events_created
            self._emit_agent_log(
                db=db,
                run_id=run.id,
                source_key=None,
                agent=EventAgent.ORCHESTRATOR,
                state="DONE",
                decision="run_completed",
                reason="all_sources_processed",
                payload={
                    "sources_processed": sources_processed,
                    "chunks_processed": chunks_processed,
                    "events_created": events_created,
                },
            )
            db.commit()
            db.refresh(run)
        except Exception as exc:
            db.rollback()
            run.status = EventRunStatus.FAILED
            run.error_message = str(exc)
            run.completed_at = func.now()
            self._emit_agent_log(
                db=db,
                run_id=run.id,
                source_key=None,
                agent=EventAgent.ORCHESTRATOR,
                state="FAILED",
                decision="run_failed",
                reason="exception",
                payload={"error": str(exc)},
            )
            db.commit()
            db.refresh(run)
            logger.exception("Event pipeline run failed", exc_info=exc)
            raise

        return PipelineResult(
            run_id=str(run.id),
            status=run.status.value,
            sources_processed=sources_processed,
            chunks_processed=chunks_processed,
            events_created=events_created,
        )

    @staticmethod
    def _log_source(db: Session, run_id, source, status: EventSourceStatus, reason: str) -> None:
        db.flush()
        existing = (
            db.query(EventSourceLog)
            .filter(EventSourceLog.run_id == run_id, EventSourceLog.source_key == source.source_key)
            .one_or_none()
        )
        if existing is None:
            db.add(
                EventSourceLog(
                    run_id=run_id,
                    source_key=source.source_key,
                    source_url=source.canonical_url,
                    category=source.category,
                    parent_category=source.parent_category,
                    status=status,
                    reason=reason,
                    chunk_count=source.chunk_count,
                )
            )
            db.flush()
            return

        existing.status = status
        existing.reason = reason
        if status in {EventSourceStatus.DONE, EventSourceStatus.FAILED, EventSourceStatus.SKIPPED}:
            existing.completed_at = func.now()

    @staticmethod
    def _emit_agent_log(
        db: Session,
        run_id,
        source_key: str | None,
        agent: EventAgent,
        state: str,
        decision: str,
        reason: str,
        payload: dict[str, object],
    ) -> None:
        db.add(
            EventAgentLog(
                run_id=run_id,
                source_key=source_key,
                agent=agent,
                state=state,
                decision=decision,
                reason=reason,
                payload=payload,
            )
        )
