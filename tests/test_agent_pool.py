"""Tests for app.services.agent_pool."""

import pytest

from app.services.agent_pool import AgentPool, Agent, AgentStatus


class _FakeChunk:
    def __init__(self, chunk_id: str = "chunk_0") -> None:
        self.chunk_id = chunk_id


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_pool_creation():
    """Creates correct number of agents, all idle."""
    pool = AgentPool(max_agents=3)
    assert len(pool._agents) == 3
    for agent in pool._agents:
        assert agent.status == AgentStatus.IDLE


def test_pool_creation_minimum():
    """Creates a pool with 1 agent (minimum)."""
    pool = AgentPool(max_agents=1)
    assert len(pool._agents) == 1


def test_pool_creation_invalid():
    """Raises ValueError if max_agents < 1."""
    with pytest.raises(ValueError, match="max_agents must be >= 1"):
        AgentPool(max_agents=0)


# ---------------------------------------------------------------------------
# get_idle_agent
# ---------------------------------------------------------------------------


def test_get_idle_agent():
    """Returns an idle agent from the pool."""
    pool = AgentPool(max_agents=2)
    agent = pool.get_idle_agent()

    assert agent is not None
    assert agent.status == AgentStatus.IDLE


def test_get_idle_agent_all_busy():
    """Returns None when all agents are busy."""
    pool = AgentPool(max_agents=2)
    # Assign both agents
    agent0 = pool.get_idle_agent()
    pool.assign_chunk(agent0, _FakeChunk("c1"), "de", "ch_1")

    agent1 = pool.get_idle_agent()
    pool.assign_chunk(agent1, _FakeChunk("c2"), "fr", "ch_2")

    # No idle agents left
    assert pool.get_idle_agent() is None


# ---------------------------------------------------------------------------
# assign_chunk / release_agent
# ---------------------------------------------------------------------------


def test_assign_and_release():
    """Agent state changes correctly through assign → release cycle."""
    pool = AgentPool(max_agents=1)
    agent = pool.get_idle_agent()

    assert agent.status == AgentStatus.IDLE

    pool.assign_chunk(agent, _FakeChunk("c1"), "de", "ch_1")

    assert agent.status == AgentStatus.WORKING
    assert agent.current_language == "de"
    assert agent.current_chapter == "ch_1"
    assert agent.current_chunk == "c1"
    assert agent.progress == 0.0
    assert agent.retry_count == 0
    assert agent.last_error is None

    pool.release_agent(agent.agent_id)

    assert agent.status == AgentStatus.IDLE
    assert agent.current_language is None
    assert agent.current_chapter is None
    assert agent.current_chunk is None
    assert agent.progress == 0.0


# ---------------------------------------------------------------------------
# status queries
# ---------------------------------------------------------------------------


def test_get_status_summary():
    """get_status_summary returns a human-readable string."""
    pool = AgentPool(max_agents=2)
    summary = pool.get_status_summary()

    assert "2 total" in summary
    assert "2 idle" in summary


def test_get_agents_status():
    """get_agents_status returns snapshots as dicts."""
    pool = AgentPool(max_agents=2)
    statuses = pool.get_agents_status()

    assert len(statuses) == 2
    assert statuses[0]["agent_id"] == "agent_0"
    assert statuses[0]["status"] == "idle"
    assert statuses[1]["agent_id"] == "agent_1"


# ---------------------------------------------------------------------------
# resize
# ---------------------------------------------------------------------------


def test_resize_grow():
    """Pool can grow by adding new idle agents."""
    pool = AgentPool(max_agents=2)
    assert len(pool._agents) == 2

    pool.resize(5)
    assert len(pool._agents) == 5
    assert all(a.status == AgentStatus.IDLE for a in pool._agents)
    assert pool._max_agents == 5


def test_resize_shrink():
    """Pool can shrink by removing idle agents."""
    pool = AgentPool(max_agents=4)
    assert len(pool._agents) == 4

    pool.resize(2)
    assert len(pool._agents) == 2


def test_resize_shrink_preserves_busy_agents():
    """Shrinking does not remove working agents; pool may stay larger."""
    pool = AgentPool(max_agents=4)
    agent = pool.get_idle_agent()
    pool.assign_chunk(agent, _FakeChunk("c1"), "de", "ch_1")

    pool.resize(2)
    # Should keep the busy agent + at least one idle
    working = [a for a in pool._agents if a.status == AgentStatus.WORKING]
    assert len(working) == 1
    # Pool may be > 2 because busy agents can't be removed
    assert len(pool._agents) >= 2


def test_resize_invalid():
    """Raises ValueError for invalid new_max."""
    pool = AgentPool(max_agents=2)
    with pytest.raises(ValueError, match="new_max must be >= 1"):
        pool.resize(0)


# ---------------------------------------------------------------------------
# max_agents invariant
# ---------------------------------------------------------------------------


def test_max_agents_not_exceeded():
    """Pool never creates more agents than max_agents on init."""
    pool = AgentPool(max_agents=7)
    assert len(pool._agents) == 7


def test_max_agents_not_exceeded_after_grow():
    """After growing, agent count equals new max."""
    pool = AgentPool(max_agents=3)
    pool.resize(10)
    assert len(pool._agents) == 10
