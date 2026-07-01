"""Regression checks for Phase 3B behavior-case accounting.

Behavior coverage is intentionally stricter than function coverage: a replay
event must explicitly cite source_evidence.behavior_cases via source_case_ids.
Otherwise one easy event for a function could hide untested behavior variants.
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase3_evaluator.trace_replay_3b import TraceReplay3B


def main():
    temp = tempfile.TemporaryDirectory()
    temp_root = Path(temp.name)
    src_db_path = temp_root / "src.json"
    tgt_db_path = temp_root / "tgt.json"
    src_db_path.write_text(json.dumps({
        "files": {
            "calc.c": {
                "functions": [
                    {
                        "name": "add_i32",
                        "signature": "int add_i32(int left, int right)",
                        "body": "int add_i32(int left, int right) { return left + right; }",
                    }
                ]
            }
        }
    }), encoding="utf-8")
    tgt_db_path.write_text(json.dumps({
        "files": {
            "src/lib.rs": {
                "standalone_functions": [
                    {
                        "name": "add",
                        "signature": "pub fn add(left: i32, right: i32) -> i32",
                        "body": "pub fn add(left: i32, right: i32) -> i32 { left + right }",
                    }
                ]
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
        "source_evidence": {
            "summary": {
                "available_behavior_case_candidates": 2,
            },
            "quality_checks": {
                "available_behavior_case_candidates": 2,
            },
            "behavior_cases": [
                {
                    "case_id": "case_add_positive",
                    "aligned_source_functions": ["calc.c::add_i32"],
                },
                {
                    "case_id": "case_add_zero",
                    "aligned_source_functions": ["calc.c::add_i32"],
                },
            ],
        }
    }
    assert evaluator._extract_json_from_llm_reply('{"ok":true}}') == {"ok": True}
    sanitization_adapter = {
        "public_operations": {
            "good": {"source_functions": ["calc.c::add_i32"], "target_functions": ["src/lib.rs::add"]},
            "bad": {"source_functions": ["calc.c::add_i32"], "target_functions": ["src/lib.rs::add"]},
        },
        "trace_events": [
            {"id": "good", "operation": "good", "source_case_ids": ["case_add_positive"]},
            {"id": "bad", "operation": "bad", "source_case_ids": []},
        ],
        "excluded_behavior_cases": [{
            "case_id": "case_add_zero",
            "reason": "cannot_public_replay_internal_state_transition",
            "details": "Invalid for a non-mixed case.",
        }],
        "rust_test_harness": (
            "#[test]\nfn good() { assert_eq!(1, 1); }\n"
            "#[test]\nfn bad() { assert_eq!(1, 1); }\n"
        ),
    }
    evaluator._sanitize_generated_adapter(sanitization_adapter)
    assert [event["id"] for event in sanitization_adapter["trace_events"]] == ["good"]
    assert set(sanitization_adapter["public_operations"]) == {"good"}
    assert "fn bad" not in sanitization_adapter["rust_test_harness"]
    assert sanitization_adapter["excluded_behavior_cases"] == []

    adapter_without_case_ids = {
        "public_operations": {
            "add": {
                "source_functions": ["calc.c::add_i32"],
                "target_functions": ["src/lib.rs::add"],
            }
        },
        "trace_events": [
            {
                "id": "trace_add_positive",
                "operation": "add",
            }
        ],
    }
    coverage = evaluator._adapter_behavior_case_coverage(adapter_without_case_ids)
    assert coverage["required_behavior_case_count"] == 2
    assert coverage["available_behavior_case_count"] == 2
    assert coverage["replayed_behavior_case_count"] == 0
    assert coverage["missing_behavior_case_count"] == 2
    assert coverage["events_without_source_case_ids"] == ["trace_add_positive"]

    invalid_exclusion_coverage = evaluator._adapter_behavior_case_coverage({
        "trace_events": [],
        "excluded_behavior_cases": [
            {
                "case_id": "case_add_positive",
                "reason": "target_missing_public_api",
            }
        ],
    })
    assert invalid_exclusion_coverage["excluded_behavior_case_count"] == 0
    assert invalid_exclusion_coverage["missing_behavior_case_count"] == 2
    assert invalid_exclusion_coverage["invalid_excluded_behavior_cases"]

    valid_exclusion_coverage = evaluator._adapter_behavior_case_coverage({
        "trace_events": [],
        "excluded_behavior_cases": [
            {
                "case_id": "case_add_positive",
                "reason": "target_missing_public_api",
                "details": "The target parsed public API index contains no callable equivalent.",
            }
        ],
    })
    assert valid_exclusion_coverage["excluded_behavior_case_count"] == 1
    assert valid_exclusion_coverage["missing_behavior_case_count"] == 1
    assert valid_exclusion_coverage["invalid_excluded_behavior_cases"] == []

    free_text_exclusion_adapter = {
        "excluded_behavior_cases": [
            {
                "case_id": "case_add_positive",
                "reason": "Target parser does not support the source extension option.",
            }
        ],
    }
    evaluator._normalize_behavior_case_exclusions(free_text_exclusion_adapter)
    normalized_exclusion = free_text_exclusion_adapter["excluded_behavior_cases"][0]
    assert normalized_exclusion["reason"] == "Target parser does not support the source extension option."
    assert "details" not in normalized_exclusion
    normalized_coverage = evaluator._adapter_behavior_case_coverage(free_text_exclusion_adapter)
    assert normalized_coverage["excluded_behavior_case_count"] == 0
    assert normalized_coverage["missing_behavior_case_count"] == 2
    assert normalized_coverage["invalid_excluded_behavior_cases"][0]["reason"] == "unsupported_exclusion_reason"

    duplicate_exclusion_adapter = {
        "excluded_behavior_cases": [
            {
                "case_id": "case_add_positive",
                "reason": "target_missing_public_api",
                "details": "No public equivalent exists.",
            },
            {
                "case_id": "case_add_positive",
                "reason": "target_missing_public_api",
                "details": "The parsed target API index confirms the gap.",
            },
        ],
    }
    evaluator._normalize_behavior_case_exclusions(duplicate_exclusion_adapter)
    assert len(duplicate_exclusion_adapter["excluded_behavior_cases"]) == 1
    assert "parsed target API index" in duplicate_exclusion_adapter["excluded_behavior_cases"][0]["details"]

    replay_exclusion_overlap = evaluator._adapter_behavior_case_coverage({
        "public_operations": {
            "add": {"source_functions": ["calc.c::add_i32"]},
        },
        "trace_events": [
            {
                "id": "trace_add_positive",
                "operation": "add",
                "source_case_ids": ["case_add_positive"],
            }
        ],
        "excluded_behavior_cases": [
            {
                "case_id": "case_add_positive",
                "reason": "target_missing_public_api",
                "details": "Invalid overlap fixture for regression coverage.",
            }
        ],
    })
    assert replay_exclusion_overlap["replayed_behavior_case_count"] == 1
    assert replay_exclusion_overlap["excluded_behavior_case_count"] == 0
    assert replay_exclusion_overlap["replayed_and_excluded_case_ids"] == ["case_add_positive"]

    mismatched_binding_coverage = evaluator._adapter_behavior_case_coverage({
        "public_operations": {
            "other": {
                "source_functions": ["calc.c::subtract_i32"],
            }
        },
        "trace_events": [
            {
                "id": "trace_wrong_function",
                "operation": "other",
                "source_case_ids": ["case_add_positive"],
            }
        ],
    })
    assert mismatched_binding_coverage["replayed_behavior_case_count"] == 0
    assert mismatched_binding_coverage["invalid_event_case_bindings"]

    ungrounded_group_coverage = evaluator._adapter_behavior_case_coverage({
        "public_operations": {
            "add": {
                "source_functions": ["calc.c::add_i32"],
            }
        },
        "trace_events": [
            {
                "id": "trace_add_group",
                "operation": "add",
                "source_case_ids": ["case_add_positive", "case_add_zero"],
            }
        ],
    })
    assert ungrounded_group_coverage["replayed_behavior_case_count"] == 0
    assert ungrounded_group_coverage["invalid_event_case_bindings"]

    grounded_group_coverage = evaluator._adapter_behavior_case_coverage({
        "public_operations": {
            "add": {
                "source_functions": ["calc.c::add_i32"],
            }
        },
        "trace_events": [
            {
                "id": "trace_add_group",
                "operation": "add",
                "source_case_ids": ["case_add_positive", "case_add_zero"],
                "case_grouping_rationale": "Both cases assert the same integer-addition postcondition.",
            }
        ],
    })
    assert grounded_group_coverage["replayed_behavior_case_count"] == 2
    assert grounded_group_coverage["invalid_event_case_bindings"] == []
    mixed_case = {
        "case_id": "case_mixed",
        "non_public_aligned_call_names": ["normalize_internal"],
        "relevant_snippet": "normalize_internal(value);",
    }
    eligible_mixed = evaluator._assess_mixed_case_public_replay(
        mixed_case,
        {
            "pairs": [{
                "src_uuid": "calc.c::normalize_internal",
                "source_public": False,
                "tgt_uuids": ["src/lib.rs::normalize"],
                "target_public_flags": [{"tgt_uuid": "src/lib.rs::normalize", "is_public": True}],
            }],
        },
    )
    assert eligible_mixed["eligible"] is True
    assert eligible_mixed["substitutions"][0]["target_public_functions"] == ["src/lib.rs::normalize"]

    private_target_mixed = evaluator._assess_mixed_case_public_replay(
        mixed_case,
        {
            "pairs": [{
                "src_uuid": "calc.c::normalize_internal",
                "source_public": False,
                "tgt_uuids": ["src/lib.rs::normalize"],
                "target_public_flags": [{"tgt_uuid": "src/lib.rs::normalize", "is_public": False}],
            }],
        },
    )
    assert private_target_mixed["eligible"] is False
    assert private_target_mixed["reason"] == "internal_call_target_not_public"
    assert evaluator._is_target_public({
        "signature": "fn from(value: &str) -> JsonValue",
        "_rust_trait_name": "From<&str>",
    })
    assert evaluator._is_target_public({
        "signature": "fn eq(&self, other: &JsonValue) -> bool",
        "_rust_trait_name": "PartialEq",
    })

    adapter_without_case_ids.update({
        "target_language": "rust",
        "recorder": "adapter_declared_trace_events_v1",
        "replay_generator": "rust_inline_harness_v1",
        "rust_test_harness": (
            "#[test]\n"
            "fn trace_add_positive() {\n"
            "    assert_eq!(1 + 1, 2);\n"
            "}\n"
        ),
    })
    adapter_without_case_ids["trace_events"][0].update({
        "evidence": "tests/test_calc.c::test_add_positive",
        "expected": {"sum": 5},
        "oracle_source": "source_test_assertion",
        "oracle_confidence": "high",
    })
    validation_errors = evaluator._validate_synthesized_adapter(adapter_without_case_ids)
    assert any("source_case_ids must list covered source_evidence.behavior_cases" in error for error in validation_errors)

    repaired_adapter_fixture = {
        "target_language": "rust",
        "recorder": "adapter_declared_trace_events_v1",
        "replay_generator": "rust_inline_harness_v1",
        "public_operations": {
            "add": {
                "source_functions": ["calc.c::add_i32"],
                "target_functions": ["src/lib.rs::add"],
                "normalization": "Compare the returned integer sum.",
                "evidence": ["tests/test_calc.c::test_add_positive"],
            },
        },
        "trace_events": [{
            "id": "trace_add_positive",
            "operation": "add",
            "source_case_ids": ["case_add_positive"],
            "evidence": "tests/test_calc.c::test_add_positive",
            "expected": "The sum is 5.",
            "oracle_source": "source_test_assertion",
            "oracle_confidence": "high",
        }],
        "rust_test_harness": "#[test]\nfn trace_add_positive() { assert_eq!(add(2, 3), 5); }\n",
    }

    empty_adapter = {}
    evaluator._apply_synthesized_adapter_defaults(empty_adapter)
    empty_adapter["trace_events"] = []
    empty_adapter["excluded_behavior_cases"] = []
    empty_adapter["rust_test_harness"] = ""
    partial_candidate = {
        "adapter_patch_version": "3b.adapter_patch.v1",
        "public_operations_add": repaired_adapter_fixture["public_operations"],
        "trace_events_add": [
            repaired_adapter_fixture["trace_events"][0],
            {
                **repaired_adapter_fixture["trace_events"][0],
                "id": "trace_add_zero_missing_test",
                "source_case_ids": ["case_add_zero"],
            },
        ],
        "excluded_behavior_cases_add": [],
        "rust_test_harness_append": repaired_adapter_fixture["rust_test_harness"],
    }
    retained_adapter, retained_cases, fragment_errors = evaluator._accept_valid_case_fragments(
        empty_adapter,
        partial_candidate,
        ["case_add_positive", "case_add_zero"],
    )
    assert retained_cases == ["case_add_positive"]
    assert fragment_errors
    assert [event["id"] for event in retained_adapter["trace_events"]] == ["trace_add_positive"]

    evaluator._last_synthesis_context["source_evidence"]["behavior_cases"][0][
        "required_internal_public_substitutions"
    ] = [{
        "source_internal_function": "calc.c::normalize_internal",
        "target_public_functions": ["src/lib.rs::normalize"],
        "handling": "explicit_target_public_substitution_required",
    }]
    missing_substitution_errors = evaluator._validate_synthesized_adapter(repaired_adapter_fixture)
    assert any("requires target public substitutions" in error for error in missing_substitution_errors)
    assert any("requires target public substitutions missing" in error for error in missing_substitution_errors)
    evaluator._last_synthesis_context["source_evidence"]["behavior_cases"][0].pop(
        "required_internal_public_substitutions"
    )

    reusable_adapter = {
        "_adapter_cache_status": "reusable_after_validated_replay",
        "_eligibility_schema_version": "3b.public_replay_eligibility.v1",
        "_eligibility_case_fingerprint": "fixture-fingerprint",
        "_last_replay_status": "passed",
        "_trace_alignment_status_counts": {"fully_aligned": 1},
        "_cache_coverage_scope": {
            "source_functions_with_src_test_evidence_count": 1,
            "adapter_missing_source_function_count": 0,
            "untraced_source_function_count": 0,
            "validated_traced_source_function_count": 1,
            "required_behavior_case_count": 2,
            "replayed_behavior_case_count": 1,
            "excluded_behavior_case_count": 0,
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

    large_cases = [
        {
            "case_id": f"case_add_{index}",
            "name": f"test_add_{index}",
            "path": "tests/test_calc.c",
            "aligned_source_functions": ["calc.c::add_i32"],
            "assertions": [{"oracle_hint": "equality_oracle"}],
            "literal_samples": [str(index)],
            "relevant_snippet": f"assert(add_i32({index}, 0) == {index});",
        }
        for index in range(125)
    ]
    evaluator._last_synthesis_context = {
        "source_evidence": {
            "summary": {"available_behavior_case_candidates": 125},
            "behavior_cases": large_cases[:120],
        }
    }
    evaluator._last_behavior_case_details = {
        case["case_id"]: case for case in large_cases
    }
    initial_large_adapter = {
        "public_operations": {
            "add": {"source_functions": ["calc.c::add_i32"]},
        },
        "trace_events": [
            {
                "id": f"trace_add_{index}",
                "operation": "add",
                "source_case_ids": [f"case_add_{index}"],
            }
            for index in range(120)
        ],
    }
    truncated_coverage = evaluator._adapter_behavior_case_coverage(initial_large_adapter)
    assert truncated_coverage["required_behavior_case_count"] == 125
    assert truncated_coverage["initial_context_behavior_case_count"] == 120
    assert truncated_coverage["initial_context_unlisted_behavior_case_count"] == 5
    assert truncated_coverage["unresolved_unlisted_behavior_case_count"] == 5
    assert truncated_coverage["missing_behavior_case_count"] == 5

    targeted_scope = evaluator._targeted_adapter_generation_scope(
        scope={
            "adapter_missing_source_functions": [],
            "missing_behavior_case_ids": truncated_coverage["missing_behavior_case_ids"],
        },
        alignment_stats={
            "pairs": [
                {
                    "src_uuid": "calc.c::add_i32",
                    "tgt_uuids": ["src/lib.rs::add"],
                    "is_public_eligible": True,
                }
            ]
        },
        inventory={},
        iteration=1,
        batch_size=10,
    )
    assert targeted_scope["targeted_missing_behavior_case_ids"] == [
        f"case_add_{index}" for index in range(120, 125)
    ]
    assert len(targeted_scope["missing_behavior_case_evidence"]) == 5

    scheduling_scope = {
        "adapter_missing_source_functions": [],
        "missing_behavior_case_ids": [f"case_add_{index}" for index in range(25)],
    }
    first_batch = evaluator._targeted_adapter_generation_scope(
        scheduling_scope,
        alignment_stats={"pairs": []},
        inventory={},
        iteration=1,
        batch_size=10,
    )
    attempt_counts = {
        case_id: 1 for case_id in first_batch["targeted_missing_behavior_case_ids"]
    }
    second_batch = evaluator._targeted_adapter_generation_scope(
        scheduling_scope,
        alignment_stats={"pairs": []},
        inventory={},
        iteration=2,
        batch_size=10,
        behavior_case_attempt_counts=attempt_counts,
    )
    for case_id in second_batch["targeted_missing_behavior_case_ids"]:
        attempt_counts[case_id] = attempt_counts.get(case_id, 0) + 1
    third_batch = evaluator._targeted_adapter_generation_scope(
        scheduling_scope,
        alignment_stats={"pairs": []},
        inventory={},
        iteration=3,
        batch_size=10,
        behavior_case_attempt_counts=attempt_counts,
    )
    assert first_batch["targeted_missing_behavior_case_ids"] == [
        f"case_add_{index}" for index in range(10)
    ]
    assert second_batch["targeted_missing_behavior_case_ids"] == [
        f"case_add_{index}" for index in range(10, 20)
    ]
    assert third_batch["targeted_missing_behavior_case_ids"] == [
        *[f"case_add_{index}" for index in range(20, 25)],
        *[f"case_add_{index}" for index in range(5)],
    ]

    completed_large_adapter = dict(initial_large_adapter)
    completed_large_adapter["trace_events"] = [
        {
            "id": f"trace_add_{index}",
            "operation": "add",
            "source_case_ids": [f"case_add_{index}"],
        }
        for index in range(125)
    ]
    completed_coverage = evaluator._adapter_behavior_case_coverage(completed_large_adapter)
    assert completed_coverage["missing_behavior_case_count"] == 0
    assert completed_coverage["unresolved_unlisted_behavior_case_count"] == 0
    assert completed_coverage["replayed_behavior_case_count"] == 125

    print(json.dumps({
        "status": "passed",
        "coverage": coverage,
    }, indent=2))
    temp.cleanup()


if __name__ == "__main__":
    main()
