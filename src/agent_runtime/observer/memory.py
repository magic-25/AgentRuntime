from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InMemoryObserver:
    tool_calls: int = 0
    failures: int = 0
    denied: int = 0
    approvals: int = 0
    approval_rejected: int = 0
    timeouts: int = 0
    audit_write_failures: int = 0
    audit_fail_closed: int = 0

    def record_tool_result(self, status: str, error: str | None = None) -> None:
        self.tool_calls += 1
        if status != "success":
            self.failures += 1
        if status == "denied":
            self.denied += 1
        if status == "rejected":
            self.approval_rejected += 1
        if error == "approval.timeout":
            self.timeouts += 1

    def record_approval_requested(self) -> None:
        self.approvals += 1

    def record_audit_failure(self, fail_closed: bool) -> None:
        self.audit_write_failures += 1
        if fail_closed:
            self.audit_fail_closed += 1

    def status(self) -> dict[str, float | int]:
        total = self.tool_calls or 1
        return {
            "tool_calls": self.tool_calls,
            "failures": self.failures,
            "denied": self.denied,
            "approval_requests": self.approvals,
            "approval_rejected": self.approval_rejected,
            "timeouts": self.timeouts,
            "audit_write_failures": self.audit_write_failures,
            "audit_fail_closed": self.audit_fail_closed,
            "failure_rate": self.failures / total,
            "reject_rate": self.approval_rejected / total,
            "timeout_rate": self.timeouts / total,
        }
