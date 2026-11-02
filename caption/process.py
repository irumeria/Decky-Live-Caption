import asyncio
import os
import signal


async def terminate_group(proc):
    """The OCR worker owns a GStreamer child. Kill both on stop or a native OCR crash."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # The worker can exit before the supervisor observes its EOF.
    try:
        await asyncio.wait_for(proc.wait(), 3)
    except TimeoutError:
        # A native OCR call can block SIGTERM cleanup. Reap the full group after the grace period.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
