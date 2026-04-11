import logging
from pathlib import Path
from typing import Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

class HeartbeatScheduler:
    def __init__(self, md_path: str = "server/heartbeat/HEARTBEAT.md"):
        self.md_path = Path(md_path)
        self.scheduler = AsyncIOScheduler()
        self.agent = None
        self.jobs_config: Dict[str, Dict[str, Any]] = {}

    def set_agent(self, agent):
        self.agent = agent

    def _parse_markdown(self) -> Dict[str, Dict[str, Any]]:
        if not self.md_path.exists():
            return {}
            
        content = self.md_path.read_text(encoding="utf-8")
        lines = content.split('\n')
        jobs = {}
        current_job = None
        
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith('## '):
                current_job = line_stripped[3:].strip()
                jobs[current_job] = {"id": current_job, "enabled": False, "cron": "", "action": ""}
            elif current_job and line_stripped.startswith('- cron:'):
                val = line_stripped.split('- cron:', 1)[1].strip().strip('"').strip("'")
                jobs[current_job]['cron'] = val
            elif current_job and line_stripped.startswith('- action:'):
                val = line_stripped.split('- action:', 1)[1].strip().strip('"').strip("'")
                jobs[current_job]['action'] = val
            elif current_job and line_stripped.startswith('- enabled:'):
                val = line_stripped.split('- enabled:', 1)[1].strip().lower()
                jobs[current_job]['enabled'] = (val == 'true')
                
        return jobs

    def _save_markdown(self):
        lines = ["# Heartbeat Schedule\n"]
        for job_id, conf in self.jobs_config.items():
            lines.append(f"## {job_id}")
            lines.append(f"- cron: \"{conf.get('cron', '')}\"")
            lines.append(f"- action: \"{conf.get('action', '')}\"")
            enabled_str = 'true' if conf.get('enabled') else 'false'
            lines.append(f"- enabled: {enabled_str}\n")
            
        self.md_path.parent.mkdir(parents=True, exist_ok=True)
        self.md_path.write_text("\n".join(lines), encoding="utf-8")

    async def _execute_job(self, action: str):
        logger.info(f"Triggering heartbeat action: {action}")
        if self.agent and hasattr(self.agent, "execute_scheduled_task"):
            try:
                await self.agent.execute_scheduled_task(action)
            except Exception as e:
                logger.error(f"Error executing heartbeat task: {e}")
        else:
            logger.warning(f"Agent not set or missing 'execute_scheduled_task'. Cannot execute: {action}")

    def _load_jobs_from_file(self):
        self.jobs_config = self._parse_markdown()
        # Clear existing scheduler jobs
        for job in self.scheduler.get_jobs():
            job.remove()
        
        for job_id, conf in self.jobs_config.items():
            if conf.get('enabled'):
                self._add_to_scheduler(conf)

    def _add_to_scheduler(self, conf: dict):
        try:
            trigger = CronTrigger.from_crontab(conf['cron'])
            self.scheduler.add_job(
                self._execute_job,
                trigger=trigger,
                args=[conf['action']],
                id=conf['id'],
                replace_existing=True
            )
            logger.info(f"Scheduled heartbeat job: {conf['id']} with cron: {conf['cron']}")
        except Exception as e:
            logger.error(f"Failed to schedule job {conf['id']}: {e}")

    def start(self):
        self._load_jobs_from_file()
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Heartbeat scheduler started")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Heartbeat scheduler stopped")

    def list_jobs(self) -> List[dict]:
        return list(self.jobs_config.values())

    def add_job(self, config: dict):
        job_id = config.get("id")
        if not job_id:
            raise ValueError("Job config must include 'id'")
        
        # Merge or add new
        if job_id not in self.jobs_config:
            self.jobs_config[job_id] = {"id": job_id, "enabled": False, "cron": "", "action": ""}
            
        self.jobs_config[job_id].update(config)
        self._save_markdown()
        
        if self.jobs_config[job_id].get("enabled"):
            self._add_to_scheduler(self.jobs_config[job_id])
        elif self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Unscheduled heartbeat job: {job_id} (disabled)")

    def remove_job(self, job_id: str):
        if job_id in self.jobs_config:
            del self.jobs_config[job_id]
            self._save_markdown()
            
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed heartbeat job: {job_id}")
