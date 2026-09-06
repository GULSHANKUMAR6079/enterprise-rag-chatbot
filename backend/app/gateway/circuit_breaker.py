"""
Circuit Breaker Pattern for LLM Providers.
Maintains CLOSED, OPEN, and HALF_OPEN states to prevent cascading upstream failures.
"""
import enum
import time
from typing import Optional


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"      # Normal healthy operation
    OPEN = "OPEN"          # Provider failing, fast-fail requests to fallback
    HALF_OPEN = "HALF_OPEN"  # Testing if provider has recovered


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_time: float = 30.0
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def can_execute(self) -> bool:
        """Determines if a call can proceed through this circuit."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if now - self.last_state_change > self.recovery_time:
                # Transition to HALF_OPEN to attempt recovery probe
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            # In half open, permit a single probe request
            return True
        return False

    def record_success(self):
        """Records a successful operation, resetting the circuit to CLOSED."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def record_failure(self):
        """Records a failure. If threshold is breached, trips the circuit to OPEN."""
        self.failure_count += 1
        now = time.time()
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = now


# Global registry of circuit breakers per provider
circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(provider_name: str, threshold: int = 3, recovery_seconds: float = 30.0) -> CircuitBreaker:
    if provider_name not in circuit_breakers:
        circuit_breakers[provider_name] = CircuitBreaker(
            name=provider_name,
            failure_threshold=threshold,
            recovery_time=recovery_seconds
        )
    return circuit_breakers[provider_name]
