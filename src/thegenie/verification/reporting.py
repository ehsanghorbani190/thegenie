from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import EvidenceVerdict, RevisionAction, RevisionItem, RevisionPlan, VerificationReport


def _atomic_write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


def write_json_report(report: VerificationReport, path: str | Path) -> Path:
    payload = report.model_dump(mode="json")
    return _atomic_write(Path(path), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def revision_plan(report: VerificationReport) -> RevisionPlan:
    items: list[RevisionItem] = []
    for result in report.claims:
        if result.verdict == EvidenceVerdict.SUPPORTED:
            continue
        if result.verdict == EvidenceVerdict.QUOTE_MISMATCH:
            action = RevisionAction.REWRITE
        elif result.verdict == EvidenceVerdict.CONTRADICTED:
            action = RevisionAction.REMOVE
        elif result.possible_alternatives:
            action = RevisionAction.INSPECT_ALTERNATIVE_EVIDENCE
        else:
            action = RevisionAction.QUALIFY
        items.append(
            RevisionItem(
                claim=result.claim.text,
                verdict=result.verdict,
                action=action,
                reason="; ".join(result.reasons),
                current_evidence=result.evidence,
                possible_alternatives=result.possible_alternatives,
            )
        )
    return RevisionPlan(source=report.source, items=tuple(items))


def write_revision_plan(plan: RevisionPlan, json_path: str | Path, markdown_path: str | Path | None = None) -> tuple[Path, Path | None]:
    json_result = _atomic_write(Path(json_path), json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n")
    if markdown_path is None:
        return json_result, None
    lines = ["# Revision plan", "", plan.note, ""]
    if not plan.items:
        lines.append("No claim revisions are suggested.")
    for index, item in enumerate(plan.items, 1):
        lines.extend(
            [
                f"## {index}. {item.action}",
                "",
                f"- **Verdict:** {item.verdict}",
                f"- **Claim:** {item.claim}",
                f"- **Reason:** {item.reason}",
            ]
        )
        if item.possible_alternatives:
            lines.append(f"- **Inspect possible citations:** {', '.join(item.possible_alternatives)}")
        lines.append("")
    markdown_result = _atomic_write(Path(markdown_path), "\n".join(lines).rstrip() + "\n")
    return json_result, markdown_result
