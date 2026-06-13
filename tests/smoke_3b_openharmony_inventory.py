import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from phase3_evaluator.trace_replay_3b import TraceReplay3B


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    output_dir = Path("output") / "phase3_3b" / "openharmony_inventory_smoke"
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="cp2rs_ohos_inventory_", dir="/tmp") as temp_dir:
        source_root = Path(temp_dir) / "OpenHarmonySynthetic"
        _write(
            source_root / "foundation" / "foo" / "BUILD.gn",
            """
import("//build/test.gni")

ohos_unittest("foo_unittest") {
  module_out_path = "foo"
  sources = [ "test/foo_test.cpp" ]
}

group("unittest") {
  testonly = true
  deps = [ ":foo_unittest" ]
}
""".strip(),
        )
        _write(
            source_root / "foundation" / "foo" / "test" / "foo_test.cpp",
            """
#include <gtest/gtest.h>

class FooTest : public testing::Test {};

HWTEST_F(FooTest, ParseWorks, testing::ext::TestSize.Level1)
{
    auto value = Foo_Parse("alpha");
    EXPECT_EQ(3, Foo_Size(value));
}
""".strip(),
        )
        _write(
            source_root / "foundation" / "foo" / "device_test" / "foo_device_test.cpp",
            """
#include <gtest/gtest.h>

class FooDeviceTest : public testing::Test {};

HWTEST_F(FooDeviceTest, BoardOnly, testing::ext::TestSize.Level1)
{
    // xDevice/HDC marker: this should be inventoried but marked device-required.
    EXPECT_TRUE(Foo_Parse("device") != nullptr);
}
""".strip(),
        )

        evaluator = TraceReplay3B(
            src_name="OpenHarmonySynthetic",
            tgt_name="RustSynthetic",
            src_repo_path=source_root,
            tgt_repo_path=source_root,
            alignment_report_path=Path("unused_alignment.json"),
            src_db_path=Path("unused_src_db.json"),
            tgt_db_path=Path("unused_tgt_db.json"),
        )
        alignment_stats = {
            "public_eligible_source_functions": [
                "foo.c::Foo_Parse",
                "foo.c::Foo_Size",
            ]
        }
        inventory = evaluator.discover_tests(alignment_stats)

    test_files = inventory.get("test_files", [])
    summary = inventory.get("summary", {})
    frameworks = summary.get("framework_files", {})
    assert summary.get("test_files") == 3, summary
    assert summary.get("build_targets") >= 2, summary
    assert frameworks.get("openharmony_gn_unittest") == 1, frameworks
    assert frameworks.get("openharmony_hwtest") == 2, frameworks
    assert summary.get("device_required_files") == 1, summary
    assert any(
        item.get("skip_reason") == "skipped_device_required"
        for item in test_files
    ), test_files
    assert any(
        {"Foo_Parse", "Foo_Size"}.issubset(set(item.get("calls_aligned_public_functions", [])))
        for item in test_files
    ), test_files

    output_path = output_dir / "test_inventory.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": "passed",
        "output": output_path.as_posix(),
        "summary": summary,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
