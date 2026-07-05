"""Regression checks for Phase 3B replay-event behavior-case accounting."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase3_evaluator.trace_replay_3b import TraceReplay3B


def make_event(event_id, case_ids, source_functions=None, target_functions=None, body=None):
    source_functions = source_functions or ["calc.c::add_i32"]
    target_functions = target_functions or ["src/lib.rs::add"]
    return {
        "id": event_id,
        "description": "Replay integer addition behavior.",
        "source_case_ids": case_ids,
        "source_functions": source_functions,
        "target_functions": target_functions,
        "normalization": "Compare returned integer sum.",
        "evidence": "tests/test_calc.c source assertion",
        "input": {"case": event_id},
        "expected": {"sum": "source asserted value"},
        "expected_behavior_source": "source_test_assertion",
        "expected_behavior_confidence": "high",
        "rust_test_body": body or f"#[test]\nfn {event_id}() {{ assert_eq!(1 + 1, 2); }}\n",
    }


def main():
    temp = tempfile.TemporaryDirectory()
    temp_root = Path(temp.name)
    src_db_path = temp_root / "src.json"
    tgt_db_path = temp_root / "tgt.json"
    src_db_path.write_text(json.dumps({
        "files": {
            "calc.c": {
                "functions": [{
                    "name": "add_i32",
                    "signature": "int add_i32(int left, int right)",
                    "body": "int add_i32(int left, int right) { return left + right; }",
                }]
            }
        }
    }), encoding="utf-8")
    tgt_db_path.write_text(json.dumps({
        "files": {
            "src/lib.rs": {
                "standalone_functions": [{
                    "name": "add",
                    "signature": "pub fn add(left: i32, right: i32) -> i32",
                    "body": "pub fn add(left: i32, right: i32) -> i32 { left + right }",
                }]
            }
        }
    }), encoding="utf-8")

    evaluator = TraceReplay3B(
        src_name="MiniCalcC",
        tgt_name="mini_calc",
        src_repo_path=Path("."),
        tgt_repo_path=Path("."),
        alignment_report_path=temp_root / "missing_alignment.json",
        src_db_path=src_db_path,
        tgt_db_path=tgt_db_path,
    )
    evaluator._last_synthesis_context = {
        "alignment_scope": {
            "public_eligible_pairs_with_src_test_evidence": [{
                "src_uuid": "calc.c::add_i32",
                "tgt_uuids": ["src/lib.rs::add"],
            }],
        },
        "source_evidence": {
            "summary": {"available_behavior_case_candidates": 2},
            "quality_checks": {"available_behavior_case_candidates": 2},
            "behavior_cases": [
                {"case_id": "case_add_positive", "aligned_source_functions": ["calc.c::add_i32"]},
                {"case_id": "case_add_zero", "aligned_source_functions": ["calc.c::add_i32"]},
            ],
        },
    }

    assert evaluator._extract_json_from_llm_reply('{"ok":true}}') == {"ok": True}

    adapter = {
        "adapter_schema_version": "3b.replay_adapter.v2",
        "target_language": "rust",
        "replay_events": [
            make_event("trace_add_positive", ["case_add_positive"]),
            make_event("trace_missing_case_ids", []),
        ],
        "unresolved_behavior_cases": [{
            "case_id": "case_add_zero",
            "reason": "unresolved_behavior_case_conversion",
            "details": "Generator did not produce a reliable replay event.",
        }],
    }
    evaluator._sanitize_generated_adapter(adapter)
    assert [event["id"] for event in adapter["replay_events"]] == ["trace_add_positive"]
    assert adapter["unresolved_behavior_cases"][0]["case_id"] == "case_add_zero"

    coverage = evaluator._adapter_behavior_case_coverage(adapter)
    assert coverage["required_behavior_case_count"] == 2
    assert coverage["replayed_behavior_case_count"] == 1
    assert coverage["unresolved_behavior_case_count"] == 1
    assert coverage["missing_behavior_case_count"] == 0

    adapter_without_case_ids = {
        "adapter_schema_version": "3b.replay_adapter.v2",
        "target_language": "rust",
        "replay_events": [make_event("trace_add_positive", [])],
    }
    coverage_without_ids = evaluator._adapter_behavior_case_coverage(adapter_without_case_ids)
    assert coverage_without_ids["replayed_behavior_case_count"] == 0
    assert coverage_without_ids["missing_behavior_case_count"] == 2
    assert coverage_without_ids["events_without_source_case_ids"] == ["trace_add_positive"]

    mismatched_binding_coverage = evaluator._adapter_behavior_case_coverage({
        "adapter_schema_version": "3b.replay_adapter.v2",
        "target_language": "rust",
        "replay_events": [
            make_event(
                "trace_wrong_function",
                ["case_add_positive"],
                source_functions=["calc.c::subtract_i32"],
            )
        ],
    })
    assert mismatched_binding_coverage["replayed_behavior_case_count"] == 0
    assert mismatched_binding_coverage["invalid_event_case_bindings"]

    valid_adapter = {
        "adapter_schema_version": "3b.replay_adapter.v2",
        "target_language": "rust",
        "replay_events": [make_event("trace_add_positive", ["case_add_positive"])],
    }
    validation_errors = evaluator._validate_synthesized_adapter(valid_adapter)
    assert not validation_errors, validation_errors

    invalid_adapter = {
        "adapter_schema_version": "3b.replay_adapter.v2",
        "target_language": "rust",
        "replay_events": [make_event("trace_add_positive", [])],
    }
    validation_errors = evaluator._validate_synthesized_adapter(invalid_adapter)
    assert any("source_case_ids must list covered" in error for error in validation_errors)

    empty_adapter = {}
    evaluator._apply_synthesized_adapter_defaults(empty_adapter)
    partial_candidate = {
        "adapter_patch_version": "3b.replay_events_patch.v1",
        "replay_events_add": [
            make_event("trace_add_positive", ["case_add_positive"]),
            {
                **make_event("trace_add_zero_missing_body", ["case_add_zero"]),
                "rust_test_body": "",
            },
        ],
        "unresolved_behavior_cases_add": [],
    }
    retained_adapter, retained_cases, fragment_errors = evaluator._accept_valid_case_fragments(
        empty_adapter,
        partial_candidate,
        ["case_add_positive", "case_add_zero"],
        scoped_pairs=[{"src_uuid": "calc.c::add_i32", "tgt_uuids": ["src/lib.rs::add"]}],
    )
    assert retained_cases == ["case_add_positive"]
    assert fragment_errors
    assert [event["id"] for event in retained_adapter["replay_events"]] == ["trace_add_positive"]

    reusable_adapter = {
        "adapter_schema_version": "3b.replay_adapter.v2",
        "_adapter_cache_status": "reusable_after_validated_replay",
        "_eligibility_schema_version": "3b.public_replay_eligibility.v1",
        "_eligibility_case_fingerprint": "fixture-fingerprint",
        "_last_replay_status": "passed",
        "_replay_plan_alignment_status_counts": {"fully_aligned": 1},
        "_cache_coverage_scope": {
            "source_functions_with_src_test_evidence_count": 1,
            "adapter_missing_source_function_count": 0,
            "untraced_source_function_count": 0,
            "validated_traced_source_function_count": 1,
            "required_behavior_case_count": 2,
            "replayed_behavior_case_count": 1,
            "unresolved_behavior_case_count": 0,
            "missing_behavior_case_count": 1,
            "unresolved_unlisted_behavior_case_count": 0,
        },
    }
    assert not TraceReplay3B._is_reusable_generated_adapter_cache_static(reusable_adapter)
    reusable_adapter["_cache_coverage_scope"].update({
        "replayed_behavior_case_count": 2,
        "missing_behavior_case_count": 0,
    })
    assert TraceReplay3B._is_reusable_generated_adapter_cache_static(reusable_adapter)

    print(json.dumps({
        "status": "passed",
        "coverage": coverage,
    }, indent=2))
    temp.cleanup()


if __name__ == "__main__":
    main()
