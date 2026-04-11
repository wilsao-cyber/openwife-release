import pytest
import asyncio
from pathlib import Path

@pytest.fixture
def temp_md(tmp_path):
    md_file = tmp_path / "HEARTBEAT.md"
    content = """# Heartbeat Schedule

## test_job
- cron: "0 9 * * *"
- action: "Test action"
- enabled: true

## disabled_job
- cron: "*/5 * * * *"
- action: "Disabled action"
- enabled: false
"""
    md_file.write_text(content, encoding="utf-8")
    return str(md_file)

@pytest.fixture
def scheduler(temp_md):
    from heartbeat.scheduler import HeartbeatScheduler
    sch = HeartbeatScheduler(md_path=temp_md)
    sch._load_jobs_from_file()
    return sch

def test_parse_markdown(scheduler):
    jobs = scheduler.jobs_config
    assert "test_job" in jobs
    assert jobs["test_job"]["cron"] == "0 9 * * *"
    assert jobs["test_job"]["action"] == "Test action"
    assert jobs["test_job"]["enabled"] is True

    assert "disabled_job" in jobs
    assert jobs["disabled_job"]["enabled"] is False

def test_list_jobs(scheduler):
    jobs = scheduler.list_jobs()
    assert len(jobs) == 2
    ids = [j["id"] for j in jobs]
    assert "test_job" in ids
    assert "disabled_job" in ids

def test_add_job_and_save(temp_md):
    from heartbeat.scheduler import HeartbeatScheduler
    sch = HeartbeatScheduler(md_path=temp_md)
    sch._load_jobs_from_file()
    
    new_job = {
        "id": "new_task",
        "cron": "0 12 * * *",
        "action": "New action",
        "enabled": True
    }
    sch.add_job(new_job)
    
    assert "new_task" in sch.jobs_config
    assert sch.scheduler.get_job("new_task") is not None
    
    sch2 = HeartbeatScheduler(md_path=temp_md)
    jobs2 = sch2._parse_markdown()
    assert "new_task" in jobs2
    assert jobs2["new_task"]["action"] == "New action"
    assert jobs2["new_task"]["enabled"] is True

def test_remove_job(scheduler, temp_md):
    from heartbeat.scheduler import HeartbeatScheduler
    assert "test_job" in scheduler.jobs_config
    scheduler.remove_job("test_job")
    assert "test_job" not in scheduler.jobs_config
    assert scheduler.scheduler.get_job("test_job") is None
    
    sch2 = HeartbeatScheduler(md_path=temp_md)
    jobs2 = sch2._parse_markdown()
    assert "test_job" not in jobs2

class DummyAgent:
    def __init__(self):
        self.called_actions = []
        
    async def execute_scheduled_task(self, action: str):
        self.called_actions.append(action)

@pytest.mark.asyncio
async def test_execute_job(scheduler):
    agent = DummyAgent()
    scheduler.set_agent(agent)
    
    await scheduler._execute_job("Test action string")
    assert len(agent.called_actions) == 1
    assert agent.called_actions[0] == "Test action string"
