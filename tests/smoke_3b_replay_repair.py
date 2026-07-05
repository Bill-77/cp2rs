"""Smoke test for Phase 3B replay-event infrastructure repair."""

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
        self.case_id = None

    def chat_completion(self, messages, temperature=0.1, model=None, max_tokens=8192):
        self.calls += 1
        prompt = messages[-1]["content"]
        if "Replay Event Repair" in prompt:
            return json.dumps({
                "replay_repair_patch_version": "3b.replay_repair_patch.v2",
                "rust_test_replacements": [{
                    "test_name": "trace_add_positive",
                    "rust_test_body": (
                        "#[test]\n"
                        "fn trace_add_positive() {\n"
                        "    use mini_calc::add;\n"
                        "    assert_eq!(add(2, 3), 5);\n"
                        "}\n"
                    ),
                }],
            }, indent=2)

        context = json.loads(prompt.split("Generation context:", 1)[1].strip())
        self.case_id = context["targeted_behavior_case_ids"][0]
        return json.dumps({
            "adapter_case_generation_version": "3b.replay_events.v1",
            "case_results": [{
                "case_id": self.case_id,
                "status": "replay_generated",
                "replay_event": {
                    "id": "trace_add_positive",
                    "description": "Add two positive integers and observe the returned sum.",
                    "source_case_ids": [self.case_id],
                    "source_functions": ["calc.c::add_i32"],
                    "target_functions": ["src/lib.rs::add"],
                    "normalization": "Compare returned integer sum.",
                    "evidence": "tests/test_calc.c::test_add_positive asserts add_i32(2, 3) == 5",
                    "input": {"left": 2, "right": 3},
                    "expected": {"sum": 5},
                    "expected_behavior_source": "source_test_assertion",
                    "expected_behavior_confidence": "high",
                    "rust_test_body": (
                        "#[test]\n"
                        "fn trace_add_positive() {\n"
                        "    use mini_calc::add;\n"
                        "    assert_eq!(add(\"2\", \"3\"), 5);\n"
                        "}\n"
                    ),
                },
            }],
        }, indent=2)


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
        "int add_i32(int left, int right);\n"
        "void test_add_positive(void) { assert(add_i32(2, 3) == 5); }\n",
        encoding="utf-8",
    )

    (tgt_repo / "src").mkdir(parents=True)
    (tgt_repo / "Cargo.toml").write_text(
        "[package]\nname = \"mini-calc\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n"
        "[lib]\nname = \"mini_calc\"\npath = \"src/lib.rs\"\n",
        encoding="utf-8",
    )
    (tgt_repo / "src" / "lib.rs").write_text(
        "pub fn add(left: i32, right: i32) -> i32 { left + right }\n",
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
        keep_debug_artifacts=True,
        llm_client=llm,
    )
    report = evaluator.run(mode="run", layer="public", artifacts_dir=output_dir)
    write_json(output_dir / "report.json", report)

    adapter = json.loads((output_dir / "effective_adapter.json").read_text(encoding="utf-8"))
    summary = report.get("metrics", {}).get("basic_counts", {})
    assert llm.calls == 2, llm.calls
    assert adapter["replay_events"][0]["rust_test_body"].count('add("2", "3")') == 0
    assert report.get("target_replay", {}).get("summary", {}).get("status") == "passed", report.get("target_replay", {})
    assert summary.get("replay_events_passed") == 1, summary
    assert summary.get("source_behavior_cases_replayed") == 1, summary

    print(json.dumps({
        "status": "passed",
        "llm_calls": llm.calls,
        "summary": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
