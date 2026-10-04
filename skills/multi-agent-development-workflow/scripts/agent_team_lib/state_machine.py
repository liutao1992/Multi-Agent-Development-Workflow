from __future__ import annotations

from pathlib import Path
import re

from .core import (
    ProtocolViolation, current_state, line_field, section, section_field,
    validate_task_contract_integrity,
)

FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"PLANNING", "READY_FOR_IMPLEMENTATION", "BLOCKED", "CANCELLED"},
    "PLANNING": {"PLAN_REVIEW", "BLOCKED", "CANCELLED"},
    "PLAN_REVIEW": {"READY_FOR_IMPLEMENTATION", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
    "PLAN_REWORK": {"PLAN_REVIEW", "BLOCKED", "CANCELLED"},
    "READY_FOR_IMPLEMENTATION": {"IMPLEMENTING", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
    "IMPLEMENTING": {"READY_FOR_REVIEW", "REVIEWING", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
    "READY_FOR_REVIEW": {"REVIEWING", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
    "REVIEWING": {"REWORK", "PLAN_REWORK", "READY_FOR_FINAL_ACCEPTANCE", "ACCEPTED", "READY_FOR_REVIEW", "BLOCKED", "CANCELLED"},
    "REWORK": {"IMPLEMENTING", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
    "READY_FOR_FINAL_ACCEPTANCE": {"ACCEPTED", "REWORK", "PLAN_REWORK", "BLOCKED", "CANCELLED"},
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
    return line_field(text, field)


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


def _validate_contract_evidence(
    task: Path,
    status: str,
    text: str,
    label: str,
) -> None:
    revision, contract_hash = validate_task_contract_integrity(task, status)
    evidence_revision = _line_field(text, "Task Contract Revision")
    evidence_hash = _line_field(text, "Task Contract Hash").lower()
    if evidence_revision != str(revision) or evidence_hash != contract_hash:
        raise ProtocolViolation(
            f"{label} Task Contract Revision/Hash does not match current TASK/STATUS contract."
        )


def _artifact_text(task: Path, subdir: str, name: str) -> str:
    return _artifact(task, subdir, name).read_text(encoding="utf-8")


def _plan_approval(task: Path, status: str) -> str:
    artifact = section_field(status, "Current Plan", "Artifact")
    text = _artifact_text(task, "plans", artifact)
    _validate_contract_evidence(task, status, text, "Plan")
    return _line_field(text, "Approval Status")


def _review_result(task: Path, status: str) -> str:
    artifact = section_field(status, "Current Review", "Artifact")
    review = _artifact(task, "reviews", artifact)
    result = _first_line(review.read_text(encoding="utf-8"), "Review Result")
    return result.split()[0] if result else ""


def _review_field(text: str, field: str) -> str:
    return _line_field(text, field)


def _review_common(
    task: Path,
    status: str,
    observed_head: str,
) -> tuple[str, str, str, str]:
    review_name = section_field(status, "Current Review", "Artifact")
    text = _artifact_text(task, "reviews", review_name)
    _validate_contract_evidence(task, status, text, "Review")

    current_impl = section_field(status, "Current Implementation", "Artifact")
    _artifact(task, "implementations", current_impl)
    reviewed_impl = _review_field(text, "Reviewed Implementation")
    if reviewed_impl not in {Path(current_impl).stem, current_impl}:
        raise ProtocolViolation(
            f"Review evidence targets {reviewed_impl}, expected {Path(current_impl).stem} or {current_impl}."
        )

    status_sha = _require_full_sha(
        section_field(status, "Current Implementation", "Code Head SHA"),
        "STATUS Current Implementation Code Head SHA",
    )
    declared = _require_full_sha(
        _review_field(text, "Declared Code Head SHA"),
        "Review Declared Code Head SHA",
    )
    observed_review = _require_full_sha(
        _review_field(text, "Observed Code Head SHA"),
        "Review Observed Code Head SHA",
    )
    observed_now = _require_full_sha(observed_head, "Current observed Code Head SHA")
    return text, status_sha, declared, observed_review if observed_review else observed_now


def _validate_review_pass_or_fail(
    task: Path,
    status: str,
    observed_head: str,
    expected_result: str,
) -> None:
    text, status_sha, declared, observed_review = _review_common(task, status, observed_head)
    observed_now = _require_full_sha(observed_head, "Current observed Code Head SHA")
    if not (status_sha == declared == observed_review == observed_now):
        raise ProtocolViolation(
            "Review evidence Code Head must equal STATUS and current observed HEAD."
        )
    if _review_field(text, "Protocol Status") != "READY_FOR_REVIEW":
        raise ProtocolViolation(f"{expected_result} Review requires Protocol Status READY_FOR_REVIEW.")
    if section_field(status, "Current Review", "Protocol Status") != "READY_FOR_REVIEW":
        raise ProtocolViolation(f"STATUS protocol must be READY_FOR_REVIEW for {expected_result}.")
    for field in (
        "Unstaged Diff Clean",
        "Staged Diff Clean",
        "Status Porcelain Clean",
        "Control Plane Excluded",
    ):
        if _review_field(text, field) != "YES":
            raise ProtocolViolation(f"{expected_result} Review requires {field}: YES.")

    artifact_result = _review_result(task, status)
    status_result = section_field(status, "Current Review", "Result")
    if artifact_result != expected_result or status_result != expected_result:
        raise ProtocolViolation(
            f"STATUS and Review artifact must both declare {expected_result}."
        )

    if expected_result == "FAIL":
        blocking = section(text, "Blocking Issues")
        if not re.search(r"(?m)^### REV-\d+", blocking):
            raise ProtocolViolation("FAIL Review requires at least one blocking REV issue.")


def _validate_review_mismatch(task: Path, status: str, observed_head: str) -> None:
    text, status_sha, declared, observed_review = _review_common(task, status, observed_head)
    observed_now = _require_full_sha(observed_head, "Current observed Code Head SHA")
    if declared != status_sha:
        raise ProtocolViolation("Mismatch Review Declared Code Head must match submitted STATUS Code Head.")
    if observed_review != observed_now:
        raise ProtocolViolation("Mismatch Review Observed Code Head must match current Git HEAD.")
    if _review_field(text, "Protocol Status") != "REVIEW_TARGET_MISMATCH":
        raise ProtocolViolation("Mismatch Review artifact must declare REVIEW_TARGET_MISMATCH.")
    if section_field(status, "Current Review", "Protocol Status") != "REVIEW_TARGET_MISMATCH":
        raise ProtocolViolation("STATUS must declare REVIEW_TARGET_MISMATCH.")
    if _review_result(task, status) != "N/A" or section_field(status, "Current Review", "Result") != "N/A":
        raise ProtocolViolation("Review target mismatch requires Review Result N/A in STATUS and artifact.")


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
    _validate_contract_evidence(task, status, report, "Implementation")
    report_sha = _require_full_sha(_line_field(report, "Code Head SHA"), "IMPL Code Head SHA")
    observed = _require_full_sha(observed_head, "Observed Code Head SHA")
    if status_sha != report_sha or report_sha != observed:
        raise ProtocolViolation("STATUS / IMPL / observed Code Head SHA must match exactly.")


def _validate_acceptance(task: Path, status: str, observed_head: str) -> None:
    artifact = section_field(status, "Final Acceptance", "Artifact")
    if artifact in {"", "N/A", "None"}:
        raise ProtocolViolation("ACCEPTED requires Final Acceptance Artifact.")
    if Path(artifact).name != artifact:
        raise ProtocolViolation("Acceptance artifact reference must be a basename.")
    acceptance = task / artifact
    if not acceptance.is_file():
        raise ProtocolViolation(f"Acceptance artifact does not exist: {acceptance}")

    text = acceptance.read_text(encoding="utf-8")
    _validate_contract_evidence(task, status, text, "Acceptance")
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
    observed = _require_full_sha(observed_head, "Observed acceptance Code Head SHA")
    if not (code_head == accepted_status_sha == accepted_file_sha == observed):
        raise ProtocolViolation(
            "Accepted Code Head SHA must match current implementation and current Git HEAD."
        )


def validate_terminal_state(task: Path, status: str, observed_head: str) -> None:
    validate_task_contract_integrity(task, status)
    if current_state(status) == "ACCEPTED":
        _validate_implementation_target(task, status, observed_head)
        _validate_review_pass_or_fail(task, status, observed_head, "PASS")
        _validate_acceptance(task, status, observed_head)


def validate_transition(task: Path, before_status: str, after_status: str, observed_head: str) -> None:
    validate_task_contract_integrity(task, after_status)
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
        if section_field(after_status, "Current Plan", "Approval") != "PENDING":
            raise ProtocolViolation("Plan entering PLAN_REVIEW must have STATUS Approval PENDING.")
        if _plan_approval(task, after_status) != "PENDING":
            raise ProtocolViolation(
                "Impl cannot self-approve a Plan; Plan artifact Approval Status must be PENDING."
            )

    contract_changed = (
        section_field(before_status, "Task Contract", "Revision"),
        section_field(before_status, "Task Contract", "Hash"),
    ) != (
        section_field(after_status, "Task Contract", "Revision"),
        section_field(after_status, "Task Contract", "Hash"),
    )
    if before == "PLAN_REVIEW" and after == "PLAN_REWORK" and contract_changed:
        if section_field(before_status, "Current Plan", "Approval") != "PENDING":
            raise ProtocolViolation("A contract amendment in PLAN_REVIEW requires a pending old Plan.")
        old_plan = section_field(before_status, "Current Plan", "Artifact")
        old_text = _artifact_text(task, "plans", old_plan)
        if (
            _line_field(old_text, "Approval Status") != "PENDING"
            or _line_field(old_text, "Task Contract Revision")
            != section_field(before_status, "Task Contract", "Revision")
            or _line_field(old_text, "Task Contract Hash").lower()
            != section_field(before_status, "Task Contract", "Hash").lower()
        ):
            raise ProtocolViolation("The pending old Plan must match the previous Task Contract.")
        if section_field(after_status, "Current Plan", "Artifact") != old_plan:
            raise ProtocolViolation("The invalidated Plan reference must be retained for history.")
        if section_field(after_status, "Current Plan", "Approval") != "PENDING":
            raise ProtocolViolation("The invalidated Plan must remain pending and unmodified.")

    elif before == "PLAN_REVIEW" and after in {"READY_FOR_IMPLEMENTATION", "PLAN_REWORK"}:
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
            if _plan_approval(task, after_status) != "APPROVED":
                raise ProtocolViolation("Implementation Plan artifact must be APPROVED and bound to current Task Contract.")
        elif gate != "SKIPPED":
            raise ProtocolViolation(f"Unknown Plan Gate value: {gate}")

    if before in {"IMPLEMENTING", "READY_FOR_REVIEW"} and after in {"READY_FOR_REVIEW", "REVIEWING"}:
        _validate_implementation_target(task, after_status, observed_head)

    if before == "REVIEWING" and after == "READY_FOR_FINAL_ACCEPTANCE":
        if section_field(after_status, "Current Review", "Result") != "PASS":
            raise ProtocolViolation("READY_FOR_FINAL_ACCEPTANCE requires STATUS Review Result PASS.")
        _validate_implementation_target(task, after_status, observed_head)
        _validate_review_pass_or_fail(task, after_status, observed_head, "PASS")

    if before == "REVIEWING" and after == "REWORK":
        result = section_field(after_status, "Current Review", "Result")
        protocol = section_field(after_status, "Current Review", "Protocol Status")
        if result == "FAIL":
            _validate_review_pass_or_fail(task, after_status, observed_head, "FAIL")
        elif protocol == "REVIEW_TARGET_MISMATCH":
            _validate_review_mismatch(task, after_status, observed_head)
        else:
            raise ProtocolViolation("REVIEWING -> REWORK requires Review FAIL or REVIEW_TARGET_MISMATCH.")

    if before == "REVIEWING" and after == "READY_FOR_REVIEW":
        _validate_review_mismatch(task, after_status, observed_head)

    if before == "REWORK" and after == "IMPLEMENTING":
        rw = section_field(after_status, "Rework", "Active RW IDs")
        if rw in {"", "N/A", "None"}:
            raise ProtocolViolation("REWORK -> IMPLEMENTING requires confirmed Active RW IDs.")
        if section_field(after_status, "Workflow", "Plan Gate") == "REQUIRED":
            if _plan_approval(task, after_status) != "APPROVED":
                raise ProtocolViolation(
                    "REWORK implementation requires an APPROVED Plan bound to the current Task Contract."
                )

    if before in {"REVIEWING", "READY_FOR_FINAL_ACCEPTANCE"} and after == "ACCEPTED":
        _validate_implementation_target(task, after_status, observed_head)
        _validate_review_pass_or_fail(task, after_status, observed_head, "PASS")
        _validate_acceptance(task, after_status, observed_head)
