"""Background task manager for falgen — polls fal queue API in daemon threads."""

import threading
import time

import httpx


class BackgroundTask:
    """Tracks a single background generation job."""

    def __init__(self, task_id, endpoint_id, request_id, urls, headers):
        self.task_id = task_id
        self.endpoint_id = endpoint_id
        self.request_id = request_id
        self.urls = urls  # {status_url, response_url, cancel_url}
        self.headers = headers
        self.state = "IN_QUEUE"  # IN_QUEUE → IN_PROGRESS → COMPLETED/FAILED/CANCELLED
        self.result = None
        self.error = None
        self.elapsed = 0.0
        self.start_time = time.monotonic()
        self.tool_call_id = None  # set by app.py after submit


class TaskManager:
    """Manages background generation tasks with polling threads."""

    def __init__(self):
        self._tasks: dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._on_complete = None  # callback(task) — called from polling thread

    def set_completion_callback(self, cb):
        self._on_complete = cb

    def submit(self, endpoint_id, request_id, urls, headers) -> BackgroundTask:
        with self._lock:
            self._counter += 1
            task_id = f"task-{self._counter}"
        task = BackgroundTask(task_id, endpoint_id, request_id, urls, headers)
        with self._lock:
            self._tasks[task_id] = task
        t = threading.Thread(target=self._poll_task, args=(task,), daemon=True)
        t.start()
        return task

    def _poll_task(self, task):
        """Poll until COMPLETED or FAILED, then call completion callback."""
        interval = 0.5
        while True:
            try:
                resp = httpx.get(
                    task.urls["status_url"],
                    params={"logs": 1},
                    headers=task.headers,
                    timeout=15,
                )
                status = resp.json()
                task.state = status.get("status", task.state)
                task.elapsed = time.monotonic() - task.start_time

                if task.state == "COMPLETED":
                    result_resp = httpx.get(
                        task.urls["response_url"],
                        headers=task.headers,
                        timeout=60,
                    )
                    task.result = result_resp.json()
                    break

                if status.get("error"):
                    task.state = "FAILED"
                    error_detail = status["error"]
                    if isinstance(error_detail, dict):
                        import json as json_mod
                        task.error = json_mod.dumps(error_detail, default=str)[:500]
                    else:
                        task.error = str(error_detail)[:500]
                    break
            except Exception:
                pass  # retry on network errors

            time.sleep(interval)
            interval = min(interval * 1.2, 2.0)

        if self._on_complete:
            self._on_complete(task)

    def active_tasks(self) -> list[BackgroundTask]:
        with self._lock:
            return [t for t in self._tasks.values() if t.state in ("IN_QUEUE", "IN_PROGRESS")]

    def cancel(self, task_id):
        with self._lock:
            task = self._tasks.get(task_id)
        if task and task.state in ("IN_QUEUE", "IN_PROGRESS"):
            try:
                httpx.put(task.urls["cancel_url"], headers=task.headers, timeout=10)
            except Exception:
                pass
            task.state = "CANCELLED"
