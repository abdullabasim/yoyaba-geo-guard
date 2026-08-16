"""Bridge between synchronous Celery tasks and the async codebase.

Celery's prefork worker runs task functions synchronously. The database engine,
the HTTP client and the LLM client are all async. Naively calling
``asyncio.run()`` inside each task creates a fresh event loop every time, while
the SQLAlchemy connection pool keeps connections bound to the loop that created
them — producing ``Future attached to a different loop`` errors as soon as a
pooled connection is reused.

The fix is one persistent loop per worker *process*, created on first use and
reused by every task that process runs.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Return this process's dedicated loop, creating it once."""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
            logger.debug("Created persistent event loop for worker process")
        return _loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion on the process-wide loop."""
    loop = get_event_loop()
    return loop.run_until_complete(coro)


def shutdown_event_loop() -> None:
    """Dispose async resources and close the loop. Called on worker shutdown."""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            return
        try:
            from app.core.database import dispose_engine
            from app.core.redis_client import close_redis
            from app.llm.client import close_llm_client

            _loop.run_until_complete(dispose_engine())
            _loop.run_until_complete(close_llm_client())
            _loop.run_until_complete(close_redis())
        except Exception:
            logger.exception("Error while disposing async resources")
        finally:
            _loop.close()
            _loop = None
