from __future__ import annotations

import copy
import queue
import threading
import uuid
from datetime import datetime
from typing import Any, Callable


Processor = Callable[[dict[str, Any], Callable[[str, str], None]], dict[str, Any]]


class JobManager:
    def __init__(self, processor: Processor):
        self.processor = processor
        self.jobs: dict[str, dict[str, Any]] = {}
        self.queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        threading.Thread(target=self._worker, daemon=True, name="clipper-media-worker").start()

    def submit(self, payload: dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.condition:
            self.jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "stage": "queued",
                "detail": "等待处理",
                "created": now,
                "updated": now,
                "result": None,
                "error": None,
            }
        self.queue.put((job_id, copy.deepcopy(payload)))
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def wait(self, job_id: str, timeout: float | None = None) -> dict[str, Any] | None:
        with self.condition:
            self.condition.wait_for(
                lambda: job_id not in self.jobs
                or self.jobs[job_id]["status"] in {"done", "error"},
                timeout=timeout,
            )
            job = self.jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def _worker(self) -> None:
        while True:
            job_id, payload = self.queue.get()
            try:
                self._update(job_id, status="processing", stage="starting", detail="开始处理")

                def progress(stage: str, detail: str) -> None:
                    self._update(job_id, stage=stage, detail=detail)

                result = self.processor(payload, progress)
                self._update(
                    job_id,
                    status="done",
                    stage="done",
                    detail="Markdown 已保存",
                    result=result,
                )
            except Exception as exc:
                self._update(
                    job_id,
                    status="error",
                    stage="error",
                    detail="处理失败",
                    error=str(exc),
                )
            finally:
                self.queue.task_done()

    def _update(self, job_id: str, **changes: Any) -> None:
        with self.condition:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].update(changes)
            self.jobs[job_id]["updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
            self.condition.notify_all()
