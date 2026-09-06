"""
Bot and Abuse Scoring Engine.
Tracks repeated adversarial injection attempts, rapid errors, and excessive payload volume.
"""
import time
from collections import defaultdict
from typing import Dict, Tuple
from backend.app.core.config import settings


class AbuseDetector:
    def __init__(self):
        # Maps ip_hash or session_id -> list of (timestamp, score_increment, reason)
        self._violations: Dict[str, list[Tuple[float, int, str]]] = defaultdict(list)
        self._blocked_entities: Dict[str, float] = {}  # identifier -> unblock_timestamp

    def record_violation(self, identifier: str, severity_score: int, reason: str):
        """Records a security violation and increments abuse score."""
        now = time.time()
        self._violations[identifier].append((now, severity_score, reason))

        # Check total active score over the last 15 minutes
        cutoff = now - 900
        active_records = [r for r in self._violations[identifier] if r[0] > cutoff]
        self._violations[identifier] = active_records

        total_score = sum(r[1] for r in active_records)
        if total_score >= settings.ABUSE_SCORE_THRESHOLD:
            # Block for escalating duration (e.g., 10 minutes)
            self._blocked_entities[identifier] = now + 600

    def is_blocked(self, identifier: str) -> Tuple[bool, int]:
        """Returns True if the entity is temporarily blocked, along with remaining seconds."""
        now = time.time()
        if identifier in self._blocked_entities:
            unblock_time = self._blocked_entities[identifier]
            if now < unblock_time:
                return True, int(unblock_time - now)
            else:
                del self._blocked_entities[identifier]
        return False, 0


abuse_detector = AbuseDetector()
