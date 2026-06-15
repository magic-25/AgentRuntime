from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from agent_runtime.core.models import ApprovalDecision, ApprovalRequest


class ApprovalProvider(ABC):
    @abstractmethod
    def request(self, request: ApprovalRequest) -> ApprovalDecision:
        raise NotImplementedError


class StaticApprovalProvider(ApprovalProvider):
    def __init__(self, approved: bool, reason: str = "") -> None:
        self.approved = approved
        self.reason = reason

    def request(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=self.approved, reason=self.reason)


class TimeoutApprovalProvider(ApprovalProvider):
    def request(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=False, reason="approval.timeout", timed_out=True)


class CallbackApprovalProvider(ApprovalProvider):
    def __init__(self, callback: Callable[[ApprovalRequest], ApprovalDecision]) -> None:
        self.callback = callback

    @classmethod
    def timeout(cls) -> "CallbackApprovalProvider":
        return cls(lambda request: ApprovalDecision(approved=False, reason="approval.timeout", timed_out=True))

    def request(self, request: ApprovalRequest) -> ApprovalDecision:
        return self.callback(request)
