"""Smoke test for Phase 3B C++ -> Rust replay-event synthesis."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase3_evaluator.trace_replay_3b import TraceReplay3B


class FakeCppLLMClient:
    def __init__(self):
        self.calls = 0

    def chat_completion(self, messages, temperature=0.1, model=None, max_tokens=8192):
        self.calls += 1
        prompt = messages[0]["content"] if messages else ""
        context = json.loads(prompt.split("Generation context:", 1)[1].strip())
        case_ids = {case.get("name"): case.get("case_id") for case in context.get("targeted_behavior_cases", [])}

        events = [
            {
                "case_id": case_ids["CalculatorTest.AddsNumbers"],
                "id": "trace_cpp_struct_method_add",
                "description": "C++ struct method add returns the arithmetic sum.",
                "source_functions": ["include/calculator.hpp::calc::Calculator::add"],
                "target_functions": ["src/lib.rs::Calculator::add"],
                "support_target_functions": ["src/lib.rs::Calculator::new"],
                "evidence": "tests/calculator_test.cpp asserts calculator.add(2, 3) == 5",
                "input": {"left": 2, "right": 3},
                "expected": {"sum": 5},
                "body": (
                    "#[test]\nfn trace_cpp_struct_method_add() {\n"
                    "    use mini_cpp_calc::Calculator;\n"
                    "    let calculator = Calculator::new();\n"
                    "    assert_eq!(calculator.add(2, 3), 5);\n"
                    "}\n"
                ),
            },
            {
                "case_id": case_ids["CalculatorTest.DoublesValue"],
                "id": "trace_cpp_namespace_double_value",
                "description": "C++ namespace function doubles an integer.",
                "source_functions": ["include/calculator.hpp::calc::double_value"],
                "target_functions": ["src/lib.rs::double_value"],
                "support_target_functions": [],
                "evidence": "tests/calculator_test.cpp asserts calc::double_value(4) == 8",
                "input": {"value": 4},
                "expected": {"doubled": 8},
                "body": (
                    "#[test]\nfn trace_cpp_namespace_double_value() {\n"
                    "    use mini_cpp_calc::double_value;\n"
                    "    assert_eq!(double_value(4), 8);\n"
                    "}\n"
                ),
            },
            {
                "case_id": case_ids["CalculatorFixture.AddsViaCustomMacro"],
                "id": "trace_cpp_custom_macro_add",
                "description": "JsonCpp-style custom macro fixture calls the C++ add method.",
                "source_functions": ["include/calculator.hpp::calc::Calculator::add"],
                "target_functions": ["src/lib.rs::Calculator::add"],
                "support_target_functions": ["src/lib.rs::Calculator::new"],
                "evidence": "tests/jsoncpp_style_test.cpp asserts calculator.add(10, 5) == 15",
                "input": {"left": 10, "right": 5},
                "expected": {"sum": 15},
                "body": (
                    "#[test]\nfn trace_cpp_custom_macro_add() {\n"
                    "    use mini_cpp_calc::Calculator;\n"
                    "    let calculator = Calculator::new();\n"
                    "    assert_eq!(calculator.add(10, 5), 15);\n"
                    "}\n"
                ),
            },
        ]
        return json.dumps({
            "adapter_case_generation_version": "3b.replay_events.v1",
            "case_results": [
                {
                    "case_id": event["case_id"],
                    "status": "replay_generated",
                    "replay_event": {
                        "id": event["id"],
                        "description": event["description"],
                        "source_case_ids": [event["case_id"]],
                        "source_functions": event["source_functions"],
                        "target_functions": event["target_functions"],
                        "support_target_functions": event["support_target_functions"],
                        "normalization": "Compare the source assertion's observable integer result.",
                        "evidence": event["evidence"],
                        "input": event["input"],
                        "expected": event["expected"],
                        "expected_behavior_source": "source_test_assertion",
                        "expected_behavior_confidence": "high",
                        "rust_test_body": event["body"],
                    },
                }
                for event in events
            ],
        }, indent=2)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def build_inputs(output_dir):
    input_root = output_dir / "input"
    src_repo = input_root / "CppCalc"
    tgt_repo = input_root / "mini_cpp_calc"
    meta_dir = input_root / "meta"

    (src_repo / "include").mkdir(parents=True)
    (src_repo / "tests").mkdir(parents=True)
    (src_repo / "include" / "calculator.hpp").write_text(
        "#pragma once\n"
        "namespace calc {\n"
        "struct Calculator { int add(int left, int right) const { return left + right; } };\n"
        "inline int double_value(int value) { return value * 2; }\n"
        "}\n",
        encoding="utf-8",
    )
    (src_repo / "tests" / "calculator_test.cpp").write_text(
        "#include <gtest/gtest.h>\n#include \"calculator.hpp\"\n\n"
        "TEST(CalculatorTest, AddsNumbers) { calc::Calculator calculator; EXPECT_EQ(calculator.add(2, 3), 5); }\n"
        "TEST(CalculatorTest, DoublesValue) { EXPECT_EQ(calc::double_value(4), 8); }\n",
        encoding="utf-8",
    )
    (src_repo / "tests" / "jsoncpp_style_test.cpp").write_text(
        "#include \"calculator.hpp\"\n"
        "#define JSONTEST_ASSERT(expr) do { if (!(expr)) throw 1; } while (0)\n"
        "#define JSONTEST_FIXTURE_LOCAL(FixtureType, name) void FixtureType##_##name()\n"
        "struct CalculatorFixture {};\n"
        "JSONTEST_FIXTURE_LOCAL(CalculatorFixture, AddsViaCustomMacro) { calc::Calculator calculator; JSONTEST_ASSERT(calculator.add(10, 5) == 15); }\n",
        encoding="utf-8",
    )

    (tgt_repo / "src").mkdir(parents=True)
    (tgt_repo / "Cargo.toml").write_text(
        "[package]\nname = \"mini-cpp-calc\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n"
        "[lib]\nname = \"mini_cpp_calc\"\npath = \"src/lib.rs\"\n",
        encoding="utf-8",
    )
    (tgt_repo / "src" / "lib.rs").write_text(
        "pub struct Calculator;\n"
        "impl Calculator {\n"
        "    pub fn new() -> Self { Calculator }\n"
        "    pub fn add(&self, left: i32, right: i32) -> i32 { left + right }\n"
        "}\n"
        "pub fn double_value(value: i32) -> i32 { value * 2 }\n",
        encoding="utf-8",
    )

    alignment_path = meta_dir / "3A_alignment_CppCalc_vs_mini_cpp_calc.json"
    src_db_path = meta_dir / "CppCalc_parsed.json"
    tgt_db_path = meta_dir / "mini_cpp_calc_parsed.json"
    write_json(alignment_path, {
        "aligned_modules": [{
            "src_module": "Root",
            "tgt_module": "Root",
            "aligned_functions": [
                {"src_uuid": "include/calculator.hpp::calc::Calculator::add", "tgt_uuid": "src/lib.rs::Calculator::add", "confidence": "High"},
                {"src_uuid": "include/calculator.hpp::calc::double_value", "tgt_uuid": "src/lib.rs::double_value", "confidence": "High"},
            ],
        }]
    })
    write_json(src_db_path, {
        "metadata": {"language": "cpp"},
        "files": {
            "include/calculator.hpp": {
                "classes": [{
                    "name": "calc::Calculator",
                    "kind": "struct",
                    "has_internal_linkage": False,
                    "methods": [{
                        "name": "add",
                        "signature": "int add(int left, int right) const",
                        "body": "int add(int left, int right) const { return left + right; }",
                    }],
                }],
                "standalone_functions": [{
                    "name": "calc::double_value",
                    "signature": "inline int double_value(int value)",
                    "body": "inline int double_value(int value) { return value * 2; }",
                }],
            }
        },
    })
    write_json(tgt_db_path, {
        "metadata": {"language": "rust"},
        "files": {
            "src/lib.rs": {
                "standalone_functions": [{
                    "name": "double_value",
                    "signature": "pub fn double_value(value: i32) -> i32",
                    "body": "pub fn double_value(value: i32) -> i32 { value * 2 }",
                }],
                "impl_blocks": [{
                    "target_type": "Calculator",
                    "methods": [
                        {"name": "new", "signature": "pub fn new() -> Self", "body": "pub fn new() -> Self { Calculator }"},
                        {"name": "add", "signature": "pub fn add(&self, left: i32, right: i32) -> i32", "body": "pub fn add(&self, left: i32, right: i32) -> i32 { left + right }"},
                    ],
                }],
            }
        },
    })
    return src_repo, tgt_repo, alignment_path, src_db_path, tgt_db_path


def main():
    output_dir = Path("output") / "phase3_3b" / "cpp_adapter_pipeline_smoke"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    cache_path = TraceReplay3B.generated_adapter_cache_path("CppCalc", "mini_cpp_calc")
    if cache_path.exists():
        cache_path.unlink()

    src_repo, tgt_repo, alignment_path, src_db_path, tgt_db_path = build_inputs(output_dir)
    llm = FakeCppLLMClient()
    evaluator = TraceReplay3B(
        src_name="CppCalc",
        tgt_name="mini_cpp_calc",
        src_repo_path=src_repo,
        tgt_repo_path=tgt_repo,
        alignment_report_path=alignment_path,
        src_db_path=src_db_path,
        tgt_db_path=tgt_db_path,
        adapter_mode="synthesize",
        synthesis_attempts=1,
        keep_debug_artifacts=True,
        llm_client=llm,
    )
    report = evaluator.run(mode="run", layer="public", artifacts_dir=output_dir)
    write_json(output_dir / "report.json", report)

    adapter = json.loads((output_dir / "effective_adapter.json").read_text(encoding="utf-8"))
    context = json.loads((output_dir / "adapter_synthesis_context.json").read_text(encoding="utf-8"))
    summary = report.get("metrics", {}).get("basic_counts", {})
    assert llm.calls == 1, llm.calls
    assert context.get("source_language_context", {}).get("primary_source_language") == "cpp"
    assert len(adapter.get("replay_events", [])) == 3
    assert ("public" + "_operations") not in adapter
    assert summary.get("replay_events_executed") == 3, summary
    assert summary.get("replay_events_passed") == 3, summary
    assert summary.get("covered_aligned_pairs") == 2, summary
    assert summary.get("source_behavior_cases_replayed") == 3, summary

    print(json.dumps({
        "status": "passed",
        "llm_calls": llm.calls,
        "summary": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
