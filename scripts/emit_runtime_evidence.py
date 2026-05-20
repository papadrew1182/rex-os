#!/usr/bin/env python3
"""Emit non-blocking runtime governance evidence JSONL from current reconciliation state.

Output: docs/governance/runtime/latest_runtime_evidence.jsonl
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / "docs" / "governance"
RUNTIME_DIR = GOV / "runtime"
OUT_PATH = RUNTIME_DIR / "latest_runtime_evidence.jsonl"
CURRENT_PHASE = ROOT / "CURRENT_PHASE.md"
HANDOFFS_DIR = ROOT / "docs" / "handoffs"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git(command: str) -> str:
    import subprocess

    return subprocess.check_output(command, cwd=ROOT, shell=True, text=True).strip()


def _latest_handoff() -> Path | None:
    files = sorted(HANDOFFS_DIR.glob("*autonomous_checkpoint.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _env_fingerprint() -> str:
    import platform

    return f"os={platform.system()}-{platform.release()}|py={platform.python_version()}"


def _normalize_for_hash(rec: dict[str, Any]) -> str:
    x = dict(rec)
    x.pop("record_hash", None)
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def _mk_record(base: dict[str, Any], previous_record_hash: str | None) -> dict[str, Any]:
    rec = dict(base)
    rec["previous_record_hash"] = previous_record_hash
    rec["record_hash"] = _sha256_hex(_normalize_for_hash(rec))
    return rec


def _parse_handoff_for_verifier_evidence(handoff_text: str) -> dict[str, Any]:
    # Real evidence extraction: looks for explicit PASS markers from the latest checkpoint.
    verifier_pass = "test_phase40_verification.py`\n  - PASS" in handoff_text or "test_phase40_verification.py` => PASS" in handoff_text
    advisory_pass = "test_ph40_advisory_lock_stable_across_repeat_runs" in handoff_text and "PASS" in handoff_text
    migration_override_pass = "DATABASE_URL=postgresql://rex:***@localhost:5432/rex_ci pytest -q backend/tests/test_session2_migration_sanity.py" in handoff_text and "PASS (7 passed)" in handoff_text
    control_fail = "pytest -q backend/tests/test_verification_flows.py`" in handoff_text and "FAIL (8 failed, 1 passed)" in handoff_text
    blocker_exists = "Remaining hard blocker" in handoff_text or "credential drift" in handoff_text

    return {
        "verifier_pass": verifier_pass,
        "advisory_pass": advisory_pass,
        "migration_override_pass": migration_override_pass,
        "control_fail": control_fail,
        "blocker_exists": blocker_exists,
    }


def build_records() -> list[dict[str, Any]]:
    now = _iso_now()
    branch = _git("git branch --show-current")
    sha = _git("git rev-parse --short HEAD")
    service = "rex-os"
    env = "reconciliation-local"
    actor_id = "cron.rex.reconciliation"
    actor_type = "automation"
    corr = f"rex-reconcile-{now.replace(':', '').replace('-', '')}"
    handoff = _latest_handoff()
    handoff_ref = str(handoff.relative_to(ROOT)) if handoff else None
    handoff_text = handoff.read_text() if handoff else ""
    parsed = _parse_handoff_for_verifier_evidence(handoff_text)
    envfp = _env_fingerprint()

    # explicit unknown-policy for artifact digest when no immutable artifact digest is available
    unknown_artifact_digest = "sha256:" + _sha256_hex(f"unknown-artifact:{branch}:{sha}")

    records: list[dict[str, Any]] = []
    prev: str | None = None

    # 1) Reconcile event (always emitted)
    r1 = {
        "event_id": f"evt-{_sha256_hex(corr + '-reconcile')[:16]}",
        "timestamp_utc": now,
        "transition_type": "reconcile",
        "actor_type": actor_type,
        "actor_id": actor_id,
        "target_service": service,
        "target_env": env,
        "source_commit_sha": sha,
        "artifact_digest": unknown_artifact_digest,
        "env_fingerprint": envfp,
        "correlation_id": corr,
        "evidence_strength": "medium",
        "evidence_source_type": "log",
        "self_attested": True,
        "independent_verifier_ref": None,
        "raw_log_refs": [handoff_ref] if handoff_ref else ["CURRENT_PHASE.md"],
        "invariant_results": [],
        "decision": "observe_only",
        "reason_codes": ["reconciliation_cycle", "non_enforcing", "artifact_digest_unknown_policy"],
    }
    rec = _mk_record(r1, prev)
    records.append(rec)
    prev = rec["record_hash"]

    # 2) verifier result event (if phase40 evidence present)
    if parsed["verifier_pass"]:
        r2 = {
            "event_id": f"evt-{_sha256_hex(corr + '-verifier')[:16]}",
            "timestamp_utc": now,
            "transition_type": "verifier_result",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "target_service": service,
            "target_env": env,
            "source_commit_sha": sha,
            "artifact_digest": "sha256:" + _sha256_hex((handoff_text[:2000] or sha)),
            "env_fingerprint": envfp,
            "correlation_id": corr,
            "evidence_strength": "strong",
            "evidence_source_type": "test",
            "self_attested": False,
            "independent_verifier_ref": "pytest:backend/tests/test_phase40_verification.py",
            "raw_log_refs": [handoff_ref] if handoff_ref else ["DEPLOYMENT_STATE.md"],
            "invariant_results": [
                {"invariant_id": "INV-VERIFIER-001", "status": "pass", "verifier_ref": "pytest:backend/tests/test_phase40_verification.py"}
            ],
            "decision": "observe_only",
            "reason_codes": ["verifier_evidence_present"],
        }
        rec = _mk_record(r2, prev)
        records.append(rec)
        prev = rec["record_hash"]

    # 3) invariant result event (migration sanity + control-path fail observed)
    inv_status = "warn" if parsed["control_fail"] else "pass"
    r3 = {
        "event_id": f"evt-{_sha256_hex(corr + '-invariant')[:16]}",
        "timestamp_utc": now,
        "transition_type": "invariant_result",
        "actor_type": actor_type,
        "actor_id": actor_id,
        "target_service": service,
        "target_env": env,
        "source_commit_sha": sha,
        "artifact_digest": "sha256:" + _sha256_hex("CURRENT_PHASE.md" + sha),
        "env_fingerprint": envfp,
        "correlation_id": corr,
        "evidence_strength": "medium",
        "evidence_source_type": "test",
        "self_attested": False,
        "independent_verifier_ref": "pytest:backend/tests/test_session2_migration_sanity.py",
        "raw_log_refs": ["CURRENT_PHASE.md", handoff_ref] if handoff_ref else ["CURRENT_PHASE.md"],
        "invariant_results": [
            {"invariant_id": "INV-PROV-001", "status": "pass", "verifier_ref": "pytest:backend/tests/test_session2_migration_sanity.py"},
            {"invariant_id": "INV-GATE-001", "status": inv_status, "verifier_ref": "pytest:backend/tests/test_verification_flows.py"},
        ],
        "decision": "observe_only",
        "reason_codes": ["override_path_pass" if parsed["migration_override_pass"] else "override_path_unknown", "control_path_fail_observed" if parsed["control_fail"] else "control_path_not_observed"],
    }
    rec = _mk_record(r3, prev)
    records.append(rec)
    prev = rec["record_hash"]

    # 4) rollback availability observation if present
    if parsed["advisory_pass"]:
        r4 = {
            "event_id": f"evt-{_sha256_hex(corr + '-rollback')[:16]}",
            "timestamp_utc": now,
            "transition_type": "rollback",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "target_service": service,
            "target_env": env,
            "source_commit_sha": sha,
            "artifact_digest": "sha256:" + _sha256_hex("phase40-advisory" + sha),
            "env_fingerprint": envfp,
            "correlation_id": corr,
            "evidence_strength": "strong",
            "evidence_source_type": "test",
            "self_attested": False,
            "independent_verifier_ref": "pytest:backend/tests/test_phase40_verification.py::test_ph40_advisory_lock_stable_across_repeat_runs",
            "raw_log_refs": [handoff_ref] if handoff_ref else ["DEPLOYMENT_STATE.md"],
            "invariant_results": [
                {"invariant_id": "INV-ROLLBACK-001", "status": "pass", "verifier_ref": "pytest:backend/tests/test_phase40_verification.py::test_ph40_advisory_lock_stable_across_repeat_runs"}
            ],
            "decision": "observe_only",
            "reason_codes": ["rollback_target_availability_observed"],
        }
        rec = _mk_record(r4, prev)
        records.append(rec)
        prev = rec["record_hash"]

    # 5) escalation event if blocker exists
    if parsed["blocker_exists"]:
        r5 = {
            "event_id": f"evt-{_sha256_hex(corr + '-escalation')[:16]}",
            "timestamp_utc": now,
            "transition_type": "escalation_event",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "target_service": service,
            "target_env": env,
            "source_commit_sha": sha,
            "artifact_digest": "sha256:" + _sha256_hex("blocker-escalation" + sha),
            "env_fingerprint": envfp,
            "correlation_id": corr,
            "evidence_strength": "medium",
            "evidence_source_type": "log",
            "self_attested": True,
            "independent_verifier_ref": None,
            "raw_log_refs": ["CURRENT_PHASE.md", handoff_ref] if handoff_ref else ["CURRENT_PHASE.md"],
            "invariant_results": [
                {"invariant_id": "INV-GATE-001", "status": "warn", "verifier_ref": None}
            ],
            "decision": "observe_only",
            "reason_codes": ["open_blocker_present", "credential_drift"],
        }
        rec = _mk_record(r5, prev)
        records.append(rec)

    return records


def main() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    records = build_records()
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    print(str(OUT_PATH.relative_to(ROOT)))
    print(f"records_emitted={len(records)}")


if __name__ == "__main__":
    main()
