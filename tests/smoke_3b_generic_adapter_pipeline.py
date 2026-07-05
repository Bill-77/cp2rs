"""Smoke test for the generic Phase 3B replay-events adapter pipeline."""

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
        self.prompts = []

    def chat_completion(self, messages, temperature=0.1, model=None, max_tokens=8192):
        self.calls += 1
        prompt = messages[0]["content"] if messages else ""
        self.prompts.append(prompt)
        context = json.loads(prompt.split("Generation context:", 1)[1].strip())
        selected_case_ids = context.get("targeted_behavior_case_ids", [])

        results = []
        fixtures = [
            ("trace_add_positive", selected_case_ids[0], 2, 3, 5),
        ]
        if len(selected_case_ids) > 1:
            fixtures.append(("trace_add_zero", selected_case_ids[1], 0, 7, 7))
        for event_id, case_id, left, right, expected in fixtures:
            results.append({
                "case_id": case_id,
                "status": "replay_generated",
                "replay_event": {
                    "id": event_id,
                    "description": "Add signed integers and observe the returned sum.",
                    "source_case_ids": [case_id],
                    "source_functions": ["calc.c::add_i32"],
                    "target_functions": ["src/lib.rs::add"],
                    "normalization": "C int return and Rust i32 return are compared as the observable numeric sum.",
                    "evidence": f"tests/test_calc.c::{case_id}",
                    "input": {"left": left, "right": right},
                    "expected": {"sum": expected},
                    "expected_behavior_source": "source_test_assertion",
                    "expected_behavior_confidence": "high",
                    "rust_test_body": (
                        "#[test]\n"
                        f"fn {event_id}() {{\n"
                        "    use mini_calc::add;\n"
                        f"    assert_eq!(add({left}, {right}), {expected});\n"
                        "}\n"
                    ),
                },
            })
        return json.dumps({
            "adapter_case_generation_version": "3b.replay_events.v1",
            "case_results": results,
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
        "int add_i32(int left, int right);\n\n"
        "void test_add_positive(void) { assert(add_i32(2, 3) == 5); }\n"
        "void test_add_zero(void) { assert(add_i32(0, 7) == 7); }\n",
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
        "repository_name": "MiniCalcC",
        "language": "c",
        "files": {
            "calc.c": {
                "functions": [{
                    "name": "add_i32",
                    "signature": "int add_i32(int left, int right)",
                    "is_static": False,
                    "body": "int add_i32(int left, int right) { return left + right; }",
                }]
            }
        },
    })
    write_json(tgt_db_path, {
        "repository_name": "mini_calc",
        "language": "rust",
        "files": {
            "src/lib.rs": {
                "standalone_functions": [{
                    "name": "add",
                    "signature": "pub fn add(left: i32, right: i32) -> i32",
                    "body": "pub fn add(left: i32, right: i32) -> i32 { left + right }",
                }]
            }
        },
    })
    return src_repo, tgt_repo, alignment_path, src_db_path, tgt_db_path


def main():
    output_dir = Path("output") / "phase3_3b" / "generic_adapter_pipeline_smoke"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    cache_path = TraceReplay3B.generated_adapter_cache_path("MiniCalcC", "mini_calc")
    if cache_path.exists():
        cache_path.unlink()

    src_repo, tgt_repo, alignment_path, src_db_path, tgt_db_path = build_inputs(output_dir)
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
        agent_batch_size=2,
        keep_debug_artifacts=True,
        llm_client=llm,
    )
    report = evaluator.run(mode="run", layer="public", artifacts_dir=output_dir)
    write_json(output_dir / "report.json", report)

    adapter = json.loads((output_dir / "effective_adapter.json").read_text(encoding="utf-8"))
    replay_plan = json.loads((output_dir / "replay_plan.json").read_text(encoding="utf-8"))
    counts = report.get("metrics", {}).get("basic_counts", {})
    assert adapter.get("adapter_schema_version") == "3b.replay_adapter.v2"
    assert len(adapter.get("replay_events", [])) == 2
    assert ("public" + "_operations") not in adapter
    assert ("trace" + "_events") not in adapter
    assert replay_plan.get("schema_version") == "3b.replay_plan.v2"
    assert counts.get("replay_events_executed") == 2, counts
    assert counts.get("replay_events_passed") == 2, counts
    assert counts.get("source_behavior_cases_replayed") == 2, counts
    assert llm.calls == 1, llm.calls

    print(json.dumps({
        "status": "passed",
        "output": str(output_dir / "report.json"),
        "counts": counts,
    }, indent=2))


if __name__ == "__main__":
    main()
