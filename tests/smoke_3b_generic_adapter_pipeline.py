"""Smoke test for the generic Phase 3B adapter pipeline.

This deliberately avoids the cJSON/json-rust handcrafted adapter. It builds a
tiny source-test repository, a tiny Rust target crate, minimal parsed DBs, and a
minimal 3A report in a temp directory. A fake LLM client returns one valid
adapter so the same auto/synthesis/adapter-declared/replay path can be tested
without a network call.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase3_evaluator.trace_replay_3b import TraceReplay3B


class FakeLLMClient:
    def __init__(self):
        self.calls = 0
        self.case_ids = []
        self.prompts = []

    def chat_completion(self, messages, temperature=0.1, model=None, max_tokens=8192):
        self.calls += 1
        prompt = messages[0]["content"] if messages else ""
        self.prompts.append(prompt)
        context = json.loads(prompt.split("Generation context:", 1)[1].strip())
        selected_case_ids = context.get("targeted_behavior_case_ids", [])
        self.case_ids = list(selected_case_ids)

        trace_events = [
            {
                "id": "trace_add_positive",
                "operation": "add_numbers",
                "evidence": "tests/test_calc.c::test_add_positive asserts add_i32(2, 3) == 5",
                "input": {"left": 2, "right": 3},
                "expected": {"sum": 5},
                "oracle_source": "source_test_assertion",
                "oracle_confidence": "high",
                "source_case_ids": [selected_case_ids[0]],
            }
        ]
        rust_tests = [
            "#[test]\nfn trace_add_positive() {\n    assert_eq!(add(2, 3), 5);\n}\n"
        ]
        if len(selected_case_ids) > 1:
            trace_events.append({
                "id": "trace_add_zero",
                "operation": "add_numbers",
                "evidence": "tests/test_calc.c::test_add_zero asserts add_i32(0, 7) == 7",
                "input": {"left": 0, "right": 7},
                "expected": {"sum": 7},
                "oracle_source": "source_test_assertion",
                "oracle_confidence": "high",
                "source_case_ids": [selected_case_ids[1]],
            })
            rust_tests.append(
                "#[test]\nfn trace_add_zero() {\n    assert_eq!(add(0, 7), 7);\n}\n"
            )

        adapter = {
            "adapter_schema_version": "3b.adapter.v1",
            "name": "fake_llm_minicalc_public_v1",
            "status": "loaded",
            "adapter_role": "repo_specific_behavior_recipe",
            "generation_status": "llm_synthesized_fake_smoke",
            "recorder": "adapter_declared_trace_events_v1",
            "replay_generator": "rust_inline_harness_v1",
            "target_language": "rust",
            "target_test_command": ["cargo", "test", "--test", "cp2rs_3b_public"],
            "public_operations": {
                "add_numbers": {
                    "description": "Add signed integers and observe the returned sum.",
                    "source_functions": ["calc.c::add_i32"],
                    "target_functions": ["src/lib.rs::add"],
                    "normalization": "C int return and Rust i32 return are normalized to the observable numeric sum.",
                    "evidence": ["tests/test_calc.c::test_add_positive", "tests/test_calc.c::test_add_zero"],
                }
            },
            "trace_events": trace_events,
            "rust_test_harness": "use mini_calc::add;\n\n" + "\n".join(rust_tests),
        }
        return json.dumps({
            "adapter_patch_version": "3b.adapter_patch.v1",
            "public_operations_add": adapter["public_operations"],
            "trace_events_add": trace_events,
            "excluded_behavior_cases_add": [],
            "rust_test_harness_append": adapter["rust_test_harness"],
        }, indent=2)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    output_dir = Path("output") / "phase3_3b" / "generic_adapter_pipeline_smoke"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    cache_path = TraceReplay3B.generated_adapter_cache_path("MiniCalcC", "mini_calc")
    if cache_path.exists():
        cache_path.unlink()

    input_root = output_dir / "input"
    src_repo = input_root / "MiniCalcC"
    tgt_repo = input_root / "mini_calc"
    meta_dir = input_root / "meta"

    (src_repo / "tests").mkdir(parents=True)
    (src_repo / "calc.c").write_text(
        "int add_i32(int left, int right) { return left + right; }\n",
        encoding="utf-8",
    )
    (src_repo / "tests" / "test_calc.c").write_text(
        "#include <assert.h>\n"
        "int add_i32(int left, int right);\n\n"
        "void test_add_positive(void) {\n"
        "    assert(add_i32(2, 3) == 5);\n"
        "}\n\n"
        "void test_add_zero(void) {\n"
        "    assert(add_i32(0, 7) == 7);\n"
        "}\n\n"
        "int main(void) {\n"
        "    test_add_positive();\n"
        "    test_add_zero();\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    (tgt_repo / "src").mkdir(parents=True)
    (tgt_repo / "Cargo.toml").write_text(
        "[package]\n"
        "name = \"mini-calc\"\n"
        "version = \"0.1.0\"\n"
        "edition = \"2021\"\n\n"
        "[lib]\n"
        "name = \"mini_calc\"\n"
        "path = \"src/lib.rs\"\n",
        encoding="utf-8",
    )
    (tgt_repo / "src" / "lib.rs").write_text(
        "pub fn add(left: i32, right: i32) -> i32 {\n"
        "    left + right\n"
        "}\n",
        encoding="utf-8",
    )

    alignment_path = meta_dir / "3A_alignment_MiniCalcC_vs_mini_calc.json"
    src_db_path = meta_dir / "MiniCalcC_parsed.json"
    tgt_db_path = meta_dir / "mini_calc_parsed.json"

    write_json(alignment_path, {
        "aligned_modules": [
            {
                "src_module": "Root",
                "tgt_module": "Root",
                "aligned_functions": [
                    {
                        "src_uuid": "calc.c::add_i32",
                        "tgt_uuid": "src/lib.rs::add",
                        "confidence": "High",
                        "reason": "Both add two signed integers and return the sum.",
                    }
                ],
            }
        ]
    })
    write_json(src_db_path, {
        "repository_name": "MiniCalcC",
        "language": "c",
        "files": {
            "calc.c": {
                "functions": [
                    {
                        "name": "add_i32",
                        "signature": "int add_i32(int left, int right)",
                        "is_static": False,
                        "body": "int add_i32(int left, int right) { return left + right; }",
                    }
                ]
            }
        },
    })
    write_json(tgt_db_path, {
        "repository_name": "mini_calc",
        "language": "rust",
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
        },
    })

    llm = FakeLLMClient()
    evaluator = TraceReplay3B(
        src_name="MiniCalcC",
        tgt_name="mini_calc",
        src_repo_path=src_repo,
        tgt_repo_path=tgt_repo,
        alignment_report_path=alignment_path,
        src_db_path=src_db_path,
        tgt_db_path=tgt_db_path,
        adapter_mode="auto",
        synthesis_attempts=1,
        agent_iterations=0,
        agent_batch_size=2,
        llm_client=llm,
    )
    report = evaluator.run(mode="run", layer="public", artifacts_dir=output_dir)

    write_json(output_dir / "report.json", report)

    counts = report.get("metrics", {}).get("basic_counts", {})
    ratios = report.get("metrics", {}).get("ratio_metrics", {})
    context = json.loads((output_dir / "adapter_synthesis_context.json").read_text(encoding="utf-8"))
    eligibility = json.loads((output_dir / "public_replay_eligibility.json").read_text(encoding="utf-8"))
    assert report.get("schema_version") == "3b.report.v22"
    assert eligibility.get("schema_version") == "3b.public_replay_eligibility.v1"
    assert eligibility.get("summary", {}).get("eligible_cases_for_adapter_conversion") == 2
    assert report.get("test_selection_pipeline", {}).get("adapter_conversion_summary", {}).get("replayed_cases") == 2
    assert report.get("adapter", {}).get("generation_status") == "llm_synthesized_case_generation_v1"
    behavior_cases = context.get("source_evidence", {}).get("behavior_cases", [])
    assert behavior_cases
    assert behavior_cases[0].get("assertions")
    assert llm.calls == 1
    assert report.get("llm_usage", {}).get("calls") == 1
    assert report.get("llm_usage", {}).get("total_tokens", 0) > 0
    assert "Generation context:" in llm.prompts[0]
    assert evaluator._last_completion_budget["mode"] == "per_case_attempt_limit"
    assert evaluator._last_completion_budget["effective_iterations"] == 1
    assert report.get("adapter_case_generation", {}).get("effective_iterations") == 1
    assert cache_path.exists()
    assert counts.get("replay_events_executed") == 2
    assert counts.get("replay_events_passed") == 2
    assert counts.get("covered_aligned_pairs") == 1
    assert counts.get("available_behavior_cases") == 2
    assert counts.get("eligible_behavior_cases") == 2
    assert counts.get("replayed_behavior_cases") == 2
    assert counts.get("missing_behavior_cases") == 0
    assert ratios.get("adapter_case_generation_accounting_rate", {}).get("raw_fraction") == "2 / 2"
    assert report.get("behavior_case_coverage", {}).get("events_without_source_case_ids") == []

    cache_reuse_dir = output_dir / "cache_reuse"
    cache_reuse = TraceReplay3B(
        src_name="MiniCalcC",
        tgt_name="mini_calc",
        src_repo_path=src_repo,
        tgt_repo_path=tgt_repo,
        alignment_report_path=alignment_path,
        src_db_path=src_db_path,
        tgt_db_path=tgt_db_path,
        adapter_mode="auto",
        synthesis_attempts=1,
        llm_client=None,
    )
    reuse_report = cache_reuse.run(mode="run", layer="public", artifacts_dir=cache_reuse_dir)
    write_json(cache_reuse_dir / "report.json", reuse_report)
    reuse_counts = reuse_report.get("metrics", {}).get("basic_counts", {})
    assert reuse_report.get("adapter", {}).get("resolution") == "generated_adapter_cache"
    assert reuse_counts.get("replay_events_executed") == 2
    assert reuse_counts.get("replay_events_passed") == 2
    assert reuse_counts.get("replayed_behavior_cases") == 2

    print(json.dumps({
        "status": "passed",
        "output": str(output_dir / "report.json"),
        "cache_path": str(cache_path),
        "counts": counts,
        "cache_reuse_counts": reuse_counts,
    }, indent=2))


if __name__ == "__main__":
    main()
