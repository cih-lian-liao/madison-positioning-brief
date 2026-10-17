"""Guard rails for a public demo that spends real API money.

This lives in its own module so the counters survive Streamlit's re-runs of the page
script and are shared by every visitor of the same server process.
"""
import hashlib
import threading
import time
from collections import defaultdict, deque
from datetime import date

from .config import DAILY_RUN_LIMIT, HOURLY_RUNS_PER_VISITOR
from .errors import FriendlyError

_lock = threading.Lock()
_recent = defaultdict(deque)
_today = {"date": None, "count": 0}


def visitor_id(ip):
    """A short hash, so no IP address is ever stored or logged."""
    return hashlib.sha256((ip or "").encode()).hexdigest()[:10]


def reserver(visitor):
    """Returns a function that counts one brief against the hourly and daily limits."""
    def reserve():
        now = time.time()
        with _lock:
            q = _recent[visitor]
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= HOURLY_RUNS_PER_VISITOR:
                raise FriendlyError(
                    "You've built a lot of briefs in the last hour",
                    f"This free demo allows {HOURLY_RUNS_PER_VISITOR} briefs per hour for each visitor, because each "
                    "one uses a paid AI service.",
                    "Wait a little and try again. The brief you already built is still on this page.", kind="warn")
            today = date.today().isoformat()
            if _today["date"] != today:
                _today.update(date=today, count=0)
            if _today["count"] >= DAILY_RUN_LIMIT:
                raise FriendlyError(
                    "Today's free briefs are used up",
                    f"This demo builds up to {DAILY_RUN_LIMIT} briefs a day across all visitors, and that limit is reached.",
                    "Please come back tomorrow, or press “See an example brief” to see a finished one.", kind="warn")
            q.append(now)
            _today["count"] += 1
    return reserve
