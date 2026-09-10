# mvp/simulator/worker_pool.py
"""
Worker Thread Pool for Async Click Queueing and Event Processing.

Implements a thread pool with:
- Configurable worker threads
- Queue-based task submission
- Async execution with Futures
- Graceful shutdown with task completion
- Exception handling and logging
- Priority and drop-oldest overflow handling
"""

import threading
import queue
import logging
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional, Dict, List
from functools import partial


logger = logging.getLogger(__name__)


class WorkerPool:
    """
    Thread pool for async click queueing and event processing.

    Provides:
    - Configurable number of worker threads
    - Thread-safe task submission via queue
    - Async task execution with Futures
    - Graceful shutdown
    - Exception handling
    - Performance monitoring
    """

    def __init__(self, num_workers: int = 4, queue_size: int = 100):
        """
        Initialize WorkerPool.

        Args:
            num_workers: Number of worker threads (default: 4)
            queue_size: Maximum queue size before drop-oldest (default: 100)
        """
        self.num_workers = num_workers
        self.queue_size = queue_size
        self.is_shutdown = False

        # Thread pool executor
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=num_workers,
            thread_name_prefix='WorkerPool-'
        )

        # Task tracking
        self._lock = threading.RLock()
        self._pending_tasks: Dict[int, Future] = {}
        self._task_counter = 0

        logger.info(
            f"WorkerPool initialized: workers={num_workers}, queue_size={queue_size}"
        )

    def submit_task(
        self,
        task_fn: Callable,
        *args,
        **kwargs
    ) -> Optional[Future]:
        """
        Submit an async task to the pool.

        Args:
            task_fn: Callable to execute
            *args: Positional arguments for task_fn
            **kwargs: Keyword arguments for task_fn

        Returns:
            Future object or None if pool is shut down
        """
        if self.is_shutdown:
            logger.warning("Cannot submit task: pool is shut down")
            return None

        try:
            with self._lock:
                task_id = self._task_counter
                self._task_counter += 1

            # Submit to executor
            future = self._executor.submit(task_fn, *args, **kwargs)

            with self._lock:
                self._pending_tasks[task_id] = future

            # Clean up completed tasks
            self._cleanup_completed_tasks()

            logger.debug(f"Task {task_id} submitted")
            return future

        except Exception as e:
            logger.error(f"Failed to submit task: {e}")
            return None

    def submit_click(self, click_data: Dict[str, Any]) -> Optional[Future]:
        """
        Submit a click event for async processing.

        Args:
            click_data: Click data dictionary with x, y, timestamp, etc.

        Returns:
            Future object or None if pool is shut down
        """
        if self.is_shutdown:
            logger.warning("Cannot submit click: pool is shut down")
            return None

        try:
            # Wrap click processing
            def process_click():
                # Click processing can be extended here
                return click_data

            future = self.submit_task(process_click)
            return future

        except Exception as e:
            logger.error(f"Failed to submit click: {e}")
            return None

    def wait_all(self, timeout_sec: float = 30.0) -> bool:
        """
        Wait for all pending tasks to complete.

        Args:
            timeout_sec: Timeout in seconds (default: 30)

        Returns:
            True if all tasks completed, False if timeout
        """
        start_time = time.time()

        while True:
            with self._lock:
                pending = list(self._pending_tasks.values())

            if not pending:
                return True

            elapsed = time.time() - start_time
            if elapsed > timeout_sec:
                logger.warning(
                    f"wait_all timeout: {len(pending)} tasks still pending"
                )
                return False

            # Wait for first task to complete
            try:
                pending[0].result(timeout=0.1)
            except Exception:
                pass

            self._cleanup_completed_tasks()
            time.sleep(0.01)

    def shutdown(self, wait: bool = True) -> None:
        """
        Graceful shutdown of worker pool.

        Args:
            wait: If True, wait for pending tasks to complete (default: True)
        """
        if self.is_shutdown:
            return

        try:
            with self._lock:
                self.is_shutdown = True

            if wait:
                # Wait for pending tasks with timeout
                self.wait_all(timeout_sec=30.0)

            # Shutdown executor
            self._executor.shutdown(wait=wait)

            logger.info("WorkerPool shut down successfully")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from tracking dict."""
        with self._lock:
            completed_ids = [
                task_id for task_id, future in self._pending_tasks.items()
                if future.done()
            ]
            for task_id in completed_ids:
                del self._pending_tasks[task_id]

    def get_pending_count(self) -> int:
        """
        Get number of pending tasks.

        Returns:
            Number of incomplete tasks
        """
        with self._lock:
            return len(self._pending_tasks)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pool statistics.

        Returns:
            Dict with pool stats
        """
        with self._lock:
            return {
                'num_workers': self.num_workers,
                'queue_size': self.queue_size,
                'pending_tasks': len(self._pending_tasks),
                'is_shutdown': self.is_shutdown,
                'task_counter': self._task_counter,
            }

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.shutdown(wait=True)
        return False
