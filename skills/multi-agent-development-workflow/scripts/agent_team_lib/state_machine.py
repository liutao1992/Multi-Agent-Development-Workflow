from __future__ import annotations

from pathlib import Path
import re

from .core import ProtocolViolation, current_state, section, section_field

FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"PLANNING", "READY_FOR_IMPLEMENTATION", "BLOCKED", "CANCELLED"},
    "PLANNING": {"PLAN_REVIEW", "BLOCKED", "CANCELLED"},
    "PLAN_REVIEW": {"READY_FOR_IMPLEMENTATION", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
    "PLAN_REWORK": {"PLAN_REVIEW", "BLOCKED", "CANCELLED"},
    "READY_FOR_IMPLEMENTATION": {"IMPLEMENTING", "BLOCKED", "CANCELLED"},
    "IMPLEMENTING": {"READY_FOR_REVIEW", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
    "READY_FOR_REVIEW": {"REVIEWING", "BLOCKED", "CANCELLED"},
    "REVIEWING": {"REWORK", "READY_FOR_FINAL_ACCEPTANCE", "READY_FOR_REVIEW", "BLOCKED", "CANCELLED"},
    "REWORK": {"IMPLEMENTING", "BLOCKED", "CANCELLED"},
    "READY_FOR_FINAL_ACCEPTANCE": {"ACCEPTED", "REWORK", "BLOCKED", "CANCELLED"},
    "BLOCKED": {"CANCELLED"},
    "ACCEPTED": set(),
    "CANCELLED": set(),
}


def _first_line(text: str, heading: str) -> str:
    for line in section(text, heading).splitlines():
        value = line.strip()
        if value:
            return value
    return ""


def _line_field(text: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:\s*(.*?)\s*$", text)
    return match.group(1).strip() if match else ""


def _artifact(task: Path, subdir: str, name: str) -> Path:
    if not name or name in {"N/A", "None", "NOT_STARTED"}:
        raise ProtocolViolation(f"Required {subdir} artifact reference is missing.")
    if Path(name).name != name:
        raise ProtocolViolation(f"Artifact reference must be a basename: {name}")
    path = task / subdir / name
    if not path.is_file():
        raise ProtocolViolation(f"Referenced artifact does not exist: {path}")
    return path


def _require_full_sha(value: str, label: str) -> str:
    if not FULL_SHA.fullmatch(value or ""):
        raise ProtocolViolation(f"{label} must be a full 40-character Git SHA.")
    return value.lower()


def _plan_approval(task: Path, status: str) -> str:
    artifact = section_field(status, "Current Plan", "Artifact")
    plan = _artifact(task, "plans", artifact)
    return _line_field(plan.read_text(encoding="utf-8"), "Approval Status")


def _review_result(task: Path, status: str) -> str:
    artifact = section_field(status, "Current Review", "Artifact")
    review = _artifact(task, "reviews", artifact)
    result = _first_line(review.read_text(encoding="utf-8"), "Review Result")
    return result.split()[0] if result else ""


def _validate_implementation_target(task: Path, status: str, observed_head: str) -> None:
    artifact = section_field(status, "Current Implementation", "Artifact")
    impl = _artifact(task, "implementations", artifact)
    status_sha = _require_full_sha(
        section_field(status, "Current Implementation", "Code Head SHA"),
        "STATUS Current Implementation Code Head SHA",
    )
    frozen = section_field(status, "Current Implementation", "Review Target Frozen").lower()
    if frozen != "true":
        raise ProtocolViolation("Review Target must be frozen before review handoff.")

    report = impl.read_text(encoding="utf-8")
    report_sha = _require_full_sha(_line_field(report, "Code Head SHA"), "IMPL Code Head SHA")
    observed = _require_full_sha(observed_head, "Observed Code Head SHA")
    if status_sha != report_sha or report_sha != observed:
        raise ProtocolViolation("STATUS / IMPL / observed Code Head SHA must match exactly.")


def _validate_acceptance(task: Path, status: str) -> None:
    artifact = section_field(status, "Final Acceptance", "Artifact")
    if artifact in {"", "N/A", "None"}:
        raise ProtocolViolation("ACCEPTED requires Final Acceptance Artifact.")
    if Path(artifact).name != artifact:
        raise ProtocolViolation("Acceptance artifact reference must be a basename.")
    acceptance = task / artifact
    if not acceptance.is_file():
        raise ProtocolViolation(f"Acceptance artifact does not exist: {acceptance}")

    text = acceptance.read_text(encoding="utf-8")
    if _line_field(text, "Final Result") != "ACCEPTED":
        raise ProtocolViolation("Acceptance artifact must declare Final Result: ACCEPTED.")

    current_review = section_field(status, "Current Review", "Artifact")
    if section_field(status, "Current Review", "Result") != "PASS":
        raise ProtocolViolation("ACCEPTED requires Current Review Result PASS.")
    if _line_field(text, "Accepted Review") != current_review:
        raise ProtocolViolation("Acceptance artifact must reference the current Review.")

    code_head = _require_full_sha(
        section_field(status, "Current Implementation", "Code Head SHA"),
        "Current Implementation Code Head SHA",
    )
    accepted_status_sha = _require_full_sha(
        section_field(status, "Final Acceptance", "Accepted Code Head SHA"),
        "STATUS Accepted Code Head SHA",
    )
    accepted_file_sha = _require_full_sha(
        _line_field(text, "Accepted Code Head SHA"),
        "Acceptance Accepted Code Head SHA",
    )
    if code_head != accepted_status_sha or code_head != accepted_file_sha:
        raise ProtocolViolation("Accepted Code Head SHA must match the current implementation.")


def validate_transition(task: Path, before_status: str, after_status: str, observed_head: str) -> None:
    before = current_state(before_status)
    after = current_state(after_status)

    if before == after:
        raise ProtocolViolation(f"Lead did not perform a lifecycle transition from {before}.")

    if before == "BLOCKED":
        resume = _first_line(before_status, "Resume State")
        allowed = {resume, "CANCELLED"} if resume and resume != "N/A" else {"CANCELLED"}
        if after not in allowed:
            raise ProtocolViolation(
                f"Illegal BLOCKED transition {before} -> {after}; Resume State is {resume or 'N/A'}."
            )
    elif after not in ALLOWED_TRANSITIONS.get(before, set()):
        raise ProtocolViolation(f"Illegal lifecycle transition: {before} -> {after}")

    if after == "BLOCKED":
        resume = _first_line(after_status, "Resume State")
        if resume != before:
            raise ProtocolViolation(
                f"Entering BLOCKED must record Resume State {before}, got {resume or 'N/A'}."
            )
        return

    if after == "CANCELLED":
        return

    if before == "CREATED" and after == "READY_FOR_IMPLEMENTATION":
        gate = section_field(after_status, "Workflow", "Plan Gate")
        reason = section_field(after_status, "Workflow", "Plan Gate Skip Reason")
        if gate != "SKIPPED" or reason in {"", "N/A"}:
            raise ProtocolViolation(
                "CREATED -> READY_FOR_IMPLEMENTATION requires Plan Gate SKIPPED with a skip reason."
            )

    if before in {"PLANNING", "PLAN_REWORK"} and after == "PLAN_REVIEW":
        artifact = section_field(after_status, "Current Plan", "Artifact")
        _artifact(task, "plans", artifact)
        if section_field(after_status, "Current Plan", "Approval") not in {"PENDING", "NOT_STARTED"}:
            raise ProtocolViolation("Plan entering PLAN_REVIEW must be pending approval.")

    if before == "PLAN_REVIEW" and after in {"READY_FOR_IMPLEMENTATION", "PLAN_REWORK"}:
        expected = "APPROVED" if after == "READY_FOR_IMPLEMENTATION" else "REWORK"
        status_approval = section_field(after_status, "Current Plan", "Approval")
        file_approval = _plan_approval(task, after_status)
        if status_approval != expected or file_approval != expected:
            raise ProtocolViolation(
                f"{before} -> {after} requires Plan approval {expected} in STATUS and Plan artifact."
            )

    if before == "READY_FOR_IMPLEMENTATION" and after == "IMPLEMENTING":
        gate = section_field(after_status, "Workflow", "Plan Gate")
        if gate == "REQUIRED":
            if section_field(after_status, "Current Plan", "Approval") != "APPROVED":
                raise ProtocolViolation("Implementation requires an approved Plan.")
        elif gate != "SKIPPED":
            raise ProtocolViolation(f"Unknown Plan Gate value: {gate}")

    if before == "IMPLEMENTING" and after == "READY_FOR_REVIEW":
        _validate_implementation_target(task, after_status, observed_head)

    if before == "READY_FOR_REVIEW" and after == "REVIEWING":
        _validate_implementation_target(task, after_status, observed_head)

    if before == "REVIEWING" and after == "READY_FOR_FINAL_ACCEPTANCE":
        if section_field(after_status, "Current Review", "Result") != "PASS":
            raise ProtocolViolation("READY_FOR_FINAL_ACCEPTANCE requires STATUS Review Result PASS.")
        if _review_result(task, after_status) != "PASS":
            raise ProtocolViolation("READY_FOR_FINAL_ACCEPTANCE requires REVIEW artifact PASS.")

    if before == "REVIEWING" and after == "REWORK":
        result = section_field(after_status, "Current Review", "Result")
        protocol = section_field(after_status, "Current Review", "Protocol Status")
        if result != "FAIL" and protocol != "REVIEW_TARGET_MISMATCH":
            raise ProtocolViolation("REVIEWING -> REWORK requires Review FAIL or REVIEW_TARGET_MISMATCH.")

    if before == "REVIEWING" and after == "READY_FOR_REVIEW":
        if section_field(after_status, "Current Review", "Protocol Status") != "REVIEW_TARGET_MISMATCH":
            raise ProtocolViolation("REVIEWING -> READY_FOR_REVIEW requires REVIEW_TARGET_MISMATCH.")

    if before == "REWORK" and after == "IMPLEMENTING":
        rw = section_field(after_status, "Rework", "Active RW IDs")
        if rw in {"", "N/A", "None"}:
            raise ProtocolViolation("REWORK -> IMPLEMENTING requires confirmed Active RW IDs.")

    if before == "READY_FOR_FINAL_ACCEPTANCE" and after == "ACCEPTED":
        _validate_acceptance(task, after_status)
