import logging
import uuid
from collections.abc import Callable
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from algoplatform.models.common import Job

logger = logging.getLogger(__name__)


class OpsScheduler:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()
        self.jobs: dict[str, Job] = {}
        self._handlers: dict[str, Callable] = {}

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

    def add_job(self, name: str, handler: Callable, seconds: int = 60) -> str:
        job_id = str(uuid.uuid4())[:8]
        self._handlers[job_id] = handler

        def wrapper() -> None:
            j = self.jobs[job_id]
            j.status = "running"
            j.started = datetime.utcnow()
            try:
                handler()
                j.log_tail.append(f"[{datetime.utcnow().isoformat()}] completed")
                j.status = "completed"
            except Exception as e:
                j.log_tail.append(f"[{datetime.utcnow().isoformat()}] error: {e}")
                j.status = "failed"
            j.finished = datetime.utcnow()
            if len(j.log_tail) > 50:
                j.log_tail = j.log_tail[-50:]

        job = Job(id=job_id, name=name, status="pending", schedule=f"every {seconds}s")
        self.jobs[job_id] = job
        self.scheduler.add_job(wrapper, IntervalTrigger(seconds=seconds), id=job_id)
        return job_id

    def list_jobs(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.id)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def run_once(self, job_id: str) -> None:
        if job_id in self._handlers:
            self._handlers[job_id]()
