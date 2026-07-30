"""Generation-safe background execution independent from Kivy."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass
class _Task:
    generation: int
    cancel_event: threading.Event
    future: object = None


class BackgroundTaskManager:
    def __init__(self, schedule, max_workers=4):
        self._schedule = schedule
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="archlence",
        )
        self._lock = threading.Lock()
        self._tasks = {}
        self._generations = {}
        self._shutdown = False

    def submit(
        self,
        key,
        work,
        *,
        on_success,
        on_error,
        replace=True,
        is_target_alive=lambda: True,
    ):
        with self._lock:
            if self._shutdown:
                return None
            current = self._tasks.get(key)
            if current and current.future and not current.future.done():
                if not replace:
                    return current.future
                current.cancel_event.set()
                current.future.cancel()
            generation = self._generations.get(key, 0) + 1
            self._generations[key] = generation
            task = _Task(generation, threading.Event())
            self._tasks[key] = task

        def run():
            try:
                result = work(task.cancel_event)
            except Exception as exc:
                self._deliver(
                    key,
                    task,
                    lambda error=exc: on_error(error),
                    is_target_alive,
                )
            else:
                self._deliver(
                    key, task, lambda: on_success(result), is_target_alive
                )

        task.future = self._executor.submit(run)
        return task.future

    def _deliver(self, key, task, callback, is_target_alive):
        def apply():
            with self._lock:
                current = self._tasks.get(key)
                valid = (
                    not self._shutdown
                    and current is not None
                    and current is task
                    and current.generation == task.generation
                    and not task.cancel_event.is_set()
                )
                if valid:
                    self._tasks.pop(key, None)
            if valid and is_target_alive():
                callback()

        self._schedule(apply)

    def cancel(self, key):
        with self._lock:
            task = self._tasks.pop(key, None)
            if task:
                task.cancel_event.set()
                if task.future:
                    task.future.cancel()
            self._generations[key] = self._generations.get(key, 0) + 1

    def shutdown(self, wait=False):
        with self._lock:
            self._shutdown = True
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.cancel_event.set()
            if task.future:
                task.future.cancel()
        self._executor.shutdown(wait=wait, cancel_futures=True)
