"""Smoke test for Phase 3B replay infrastructure repair.

The fake LLM first returns a schema-valid adapter whose Rust harness calls the
target API with the wrong argument types. Schema validation passes because the
declared target API name is present, but cargo replay fails. The replay repair
prompt then receives cargo feedback and the fake LLM returns a corrected
adapter. This verifies that replay repair has a budget separate from schema
synthesis attempts.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase3_evaluator.trace_replay_3b import TraceReplay3B


class FakeReplayRepairLLM:
    def __init__(self):
        self.calls = 0

    def chat_completion(self, messages, temperature=0.1, model=None, max_tokens=8192):
        self.calls += 1
        prompt = messages[-1]["content"]
        repaired = "Phase 3B Replay Repair" in prompt
        return json.dumps(self._adapter(repaired), indent=2)

    def _adapter(self, repaired):
        if repaired:
            body = (
                "use mini_calc::add;\n\n"
                "#[test]\n"
                "fn trace_add_positive() {\n"
                "    assert_eq!(add(2, 3), 5);\n"
                "}\n"
            )
            generation_status = "llm_synthesized_repaired_fake_smoke"
        else:
            body = (
                "use mini_calc::add;\n\n"
                "#[test]\n"
                "fn trace_add_positive() {\n"
                "    assert_eq!(add(\"2\", \"3\"), 5);\n"
                "}\n"
            )
            generation_status = "llm_synthesized_needs_replay_repair_fake_smoke"

        return {
            "adapter_schema_version": "3b.adapter.v1",
            "name": "fake_replay_repair_minicalc_public_v1",
            "status": "loaded",
            "adapter_role": "repo_specific_behavior_recipe",
            "generation_status": generation_status,
            "recorder": "adapter_declared_trace_events_v1",
            "replay_generator": "rust_inline_harness_v1",
            "target_language": "rust",
            "target_test_command": ["cargo", "test", "--test", "cp2rs_3b_public"],
            "public_operations": {
                "add_positive_numbers": {
                    "description": "Add two positive integers and observe the returned sum.",
                    "source_functions": ["calc.c::add_i32"],
                    "target_functions": ["src/lib.rs::add"],
                    "normalization": "C int return and Rust i32 return are normalized to the observable numeric sum.",
                    "evidence": ["tests/test_calc.c::test_add_positive"],
                }
            },
            "trace_events": [
                {
                    "id": "trace_add_positive",
                    "operation": "add_positive_numbers",
                    "evidence": "tests/test_calc.c::test_add_positive asserts add_i32(2, 3) == 5",
                    "input": {"left": 2, "right": 3},
                    "expected": {"sum": 5},
                    "oracle_source": "source_test_assertion",
                    "oracle_confidence": "high",
                }
            ],
            "rust_test_harness": body,
        }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_inputs(output_dir):
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
        "aligned_modules": [{
            "src_module": "Root",
            "tgt_module": "Root",
            "aligned_functions": [{
                "src_uuid": "calc.c::add_i32",
                "tgt_uuid": "src/lib.rs::add",
                "confidence": "High",
            }],
        }]
    })
    write_json(src_db_path, {
        "files": {
            "calc.c": {
                "functions": [{
                    "name": "add_i32",
                    "signature": "int add_i32(int left, int right)",
                    "is_static": False,
                    "body": "int add_i32(int left, int right) { return left + right; }",
                }]
            }
        }
    })
    write_json(tgt_db_path, {
        "files": {
            "src/lib.rs": {
                "standalone_functions": [{
                    "name": "add",
                    "signature": "pub fn add(left: i32, right: i32) -> i32",
                    "body": "pub fn add(left: i32, right: i32) -> i32 { left + right }",
                }]
            }
        }
    })
    return src_repo, tgt_repo, alignment_path, src_db_path, tgt_db_path


def main():
    output_dir = Path("output") / "phase3_3b" / "replay_repair_smoke"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    src_repo, tgt_repo, alignment_path, src_db_path, tgt_db_path = build_inputs(output_dir)
    llm = FakeReplayRepairLLM()

    evaluator = TraceReplay3B(
        src_name="MiniCalcC",
        tgt_name="mini_calc",
        src_repo_path=src_repo,
        tgt_repo_path=tgt_repo,
        alignment_report_path=alignment_path,
        src_db_path=src_db_path,
        tgt_db_path=tgt_db_path,
        adapter_mode="synthesize",
        synthesis_attempts=1,
        replay_repair_attempts=1,
        llm_client=llm,
    )
    report = evaluator.run(mode="run", layer="public", artifacts_dir=output_dir)
    write_json(output_dir / "report.json", report)

    attempts = json.loads((output_dir / "adapter_synthesis_attempts.json").read_text()).get("attempts", [])
    summary = report.get("metrics", {}).get("atomic_counts", {})
    assert llm.calls == 2, llm.calls
    assert any(item.get("stage") == "replay_infrastructure_repair" for item in attempts), attempts
    assert report.get("public_behavior", {}).get("status") == "passed", report.get("public_behavior", {})
    assert summary.get("public_replay_passed") == 1, summary

    print(json.dumps({
        "status": "passed",
        "llm_calls": llm.calls,
        "attempts": attempts,
        "summary": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
