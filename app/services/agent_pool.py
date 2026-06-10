"""
Agent Pool — manages a pool of parallel translation agents.

Each Agent represents one concurrent translation worker, tracking its
current assignment, progress, and retry state.  The AgentPool is fully
thread-safe so it can be shared across worker threads.
"""

from __future__ import annotations

import enum
import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AgentStatus
# ---------------------------------------------------------------------------


class AgentStatus(enum.Enum):
    """Lifecycle status of a single translation agent."""

    IDLE = "idle"
    WORKING = "working"
    RETRY = "retry"
    ERROR = "error"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Agent dataclass
# ---------------------------------------------------------------------------


@dataclass
class Agent:
    """Immutable identity with mutable runtime state for one translation worker.

    Attributes
    ----------
    agent_id:
        Unique identifier for this agent (e.g. ``"agent_0"``).
    status:
        Current lifecycle status.
    current_language:
        Target language code of the current assignment, if any.
    current_chapter:
        Chapter id currently being processed.
    current_chunk:
        Chunk id currently being processed.
    progress:
        Normalised progress of the current assignment (0.0 – 1.0).
    chunks_completed:
        Running count of successfully translated chunks.
    chunks_failed:
        Running count of failed chunks.
    retry_count:
        Number of retries attempted for the *current* chunk.
    last_error:
        Human-readable error message from the last failure.
    """

    agent_id: str
    status: AgentStatus = AgentStatus.IDLE
    current_language: Optional[str] = None
    current_chapter: Optional[str] = None
    current_chunk: Optional[str] = None
    progress: float = 0.0
    chunks_completed: int = 0
    chunks_failed: int = 0
    retry_count: int = 0
    last_error: Optional[str] = None


# ---------------------------------------------------------------------------
# AgentPool
# ---------------------------------------------------------------------------


class AgentPool:
    """A thread-safe pool of :class:`Agent` instances.

    Parameters
    ----------
    max_agents:
        Initial pool size.
    provider:
        Optional reference to the :class:`TranslationProvider` in use.
        Stored for convenience; not called by the pool itself.
    """

    def __init__(
        self,
        max_agents: int = 4,
        provider: Optional[Any] = None,
    ) -> None:
        if max_agents < 1:
            raise ValueError(f"max_agents must be >= 1, got {max_agents}")

        self._max_agents: int = max_agents
        self._provider: Optional[Any] = provider
        self._agents: List[Agent] = []
        self._lock = threading.Lock()

        self._init_agents()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_agents(self) -> None:
        """Create exactly ``self._max_agents`` idle agents."""
        self._agents = [
            Agent(agent_id=f"agent_{i}") for i in range(self._max_agents)
        ]
        logger.debug(
            "AgentPool initialised with %d agents", self._max_agents
        )

    # ------------------------------------------------------------------
    # Pool operations
    # ------------------------------------------------------------------

    def get_idle_agent(self) -> Optional[Agent]:
        """Return the first idle agent, or ``None`` if all are busy."""
        with self._lock:
            for agent in self._agents:
                if agent.status == AgentStatus.IDLE:
                    return agent
            return None

    def assign_chunk(
        self,
        agent: Agent,
        chunk: Any,
        language: str,
        chapter_id: str,
    ) -> None:
        """Mark *agent* as working on a specific chunk.

        Parameters
        ----------
        agent:
            The agent to assign.
        chunk:
            A :class:`Chunk` (or duck-typed object) with a ``chunk_id``
            attribute.
        language:
            Target language code.
        chapter_id:
            Identifier of the owning chapter.
        """
        with self._lock:
            agent.status = AgentStatus.WORKING
            agent.current_language = language
            agent.current_chapter = chapter_id
            agent.current_chunk = chunk.chunk_id
            agent.progress = 0.0
            agent.retry_count = 0
            agent.last_error = None
            logger.debug(
                "Agent %s assigned — chapter=%s chunk=%s lang=%s",
                agent.agent_id,
                chapter_id,
                chunk.chunk_id,
                language,
            )

    def release_agent(self, agent_id: str) -> None:
        """Reset *agent_id* back to ``IDLE``.

        This does **not** update the agent's completed/failed counters;
        the caller should update those before calling release.
        """
        with self._lock:
            for agent in self._agents:
                if agent.agent_id == agent_id:
                    agent.status = AgentStatus.IDLE
                    agent.current_language = None
                    agent.current_chapter = None
                    agent.current_chunk = None
                    agent.progress = 0.0
                    break

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def get_status_summary(self) -> str:
        """Return a human-readable summary of the entire pool."""
        with self._lock:
            total = len(self._agents)
            idle = sum(1 for a in self._agents if a.status == AgentStatus.IDLE)
            working = sum(
                1 for a in self._agents if a.status == AgentStatus.WORKING
            )
            error = sum(
                1 for a in self._agents if a.status == AgentStatus.ERROR
            )
            retry = sum(
                1 for a in self._agents if a.status == AgentStatus.RETRY
            )
            completed = sum(
                1 for a in self._agents if a.status == AgentStatus.COMPLETED
            )
            return (
                f"Agents: {total} total, {idle} idle, {working} working, "
                f"{error} error, {retry} retry, {completed} completed"
            )

    def get_agents_status(self) -> List[Dict[str, Any]]:
        """Return a snapshot of every agent's state as a list of dicts."""
        with self._lock:
            return [
                {
                    "agent_id": a.agent_id,
                    "status": a.status.value,
                    "current_language": a.current_language,
                    "current_chapter": a.current_chapter,
                    "current_chunk": a.current_chunk,
                    "progress": a.progress,
                    "chunks_completed": a.chunks_completed,
                    "chunks_failed": a.chunks_failed,
                    "retry_count": a.retry_count,
                    "last_error": a.last_error,
                }
                for a in self._agents
            ]

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(self, new_max: int) -> None:
        """Grow or shrink the pool to *new_max* agents.

        When shrinking, idle agents are removed first.  If there are
        fewer idle agents than the number to remove, working agents are
        **not** forcibly killed — the pool will simply be left larger
        than *new_max* until those agents finish their current work and
        are released.
        """
        if new_max < 1:
            raise ValueError(f"new_max must be >= 1, got {new_max}")

        with self._lock:
            if new_max > self._max_agents:
                # Grow
                for i in range(self._max_agents, new_max):
                    self._agents.append(Agent(agent_id=f"agent_{i}"))
                logger.info(
                    "AgentPool grew from %d to %d agents",
                    self._max_agents,
                    new_max,
                )
            elif new_max < self._max_agents:
                # Shrink — remove idle agents only
                to_remove = self._max_agents - new_max
                surviving: List[Agent] = []
                removed = 0

                for agent in self._agents:
                    if removed < to_remove and agent.status == AgentStatus.IDLE:
                        removed += 1
                        continue
                    surviving.append(agent)

                # If we couldn't remove enough, leave the pool larger
                # temporarily.
                if len(surviving) > new_max:
                    logger.warning(
                        "Could not shrink AgentPool to %d — %d agents are busy. "
                        "Pool size is now %d.",
                        new_max,
                        len(surviving) - new_max,
                        len(surviving),
                    )

                self._agents = surviving
                logger.info(
                    "AgentPool shrunk from %d to %d agents (removed %d idle)",
                    self._max_agents,
                    len(self._agents),
                    removed,
                )

            self._max_agents = new_max
