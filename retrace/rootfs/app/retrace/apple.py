"""Keep empty Apple responses distinct from a legitimate no-sighting result."""
from findmy import AsyncAppleAccount
from findmy.errors import EmptyResponseError

class ReportSourceUnavailable(RuntimeError):
    """A stable classification; never carries the upstream response body."""

class ReportingAccount(AsyncAppleAccount):
    async def fetch_raw_reports(self, devices):
        try:
            return await super().fetch_raw_reports(devices)
        except EmptyResponseError:
            # FindMy.py's fetcher otherwise turns this protocol failure into [].
            raise ReportSourceUnavailable("empty_response") from None


class RateLimited(RuntimeError):
    """Apple asked us to stop; no response body retained."""


class PacedHttp:
    """Cross-process request spacing, with asynchronous network I/O throughout."""

    def __init__(self, delegate, gate):
        self.delegate = delegate
        self.gate = gate

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def _check_blocked(self):
        import time
        from .storage import read_json
        state=read_json(self.gate.with_name("request-cooldown.json"),{})
        if state.get("until",0)>time.time():
            raise RateLimited("rate_limited")

    def _block(self):
        import time
        from .storage import atomic_json
        atomic_json(self.gate.with_name("request-cooldown.json"),{"until":time.time()+1800})

    def _reserve(self):
        import fcntl
        import os
        import time
        self._check_blocked()
        fd = os.open(self.gate, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            now = time.time()
            try:
                previous = float(handle.read() or "0")
            except ValueError:
                previous = 0
            scheduled = max(now, min(previous, now + 5))
            handle.seek(0)
            handle.truncate()
            handle.write(str(scheduled + 1))
            handle.flush()
            return max(0, scheduled - now)

    async def post(self, *args, **kwargs):
        import asyncio
        delay = await asyncio.to_thread(self._reserve)
        await asyncio.sleep(delay)
        await asyncio.to_thread(self._check_blocked)
        response = await self.delegate.post(*args, **kwargs)
        if response.status_code == 429:
            await asyncio.to_thread(self._block)
            raise RateLimited("rate_limited")
        return response
