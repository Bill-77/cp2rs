import os
import argparse
from phase3_evaluator.macro_alignment import evaluate_macro_alignment

# 配置路径
RPG_OUTPUT_DIR = "output/rpg_graphs"
REPORT_OUTPUT_DIR = "output/evaluation_reports"

def main():
    parser = argparse.ArgumentParser(description="CP2RS Phase 3: 跨语言等价性评测总控")
    parser.add_argument("--source", type=str, required=True, help="源仓库的 RPG 文件名 (例如: cJSON_rpg.json)")
    parser.add_argument("--target", type=str, required=True, help="目标仓库的 RPG 文件名 (例如: json-rust_rpg.json)")
    args = parser.parse_args()

    source_path = os.path.join(RPG_OUTPUT_DIR, args.source)
    target_path = os.path.join(RPG_OUTPUT_DIR, args.target)

    if not os.path.exists(source_path):
        print(f"❌ 找不到源端图谱文件: {source_path}")
        return
    if not os.path.exists(target_path):
        print(f"❌ 找不到目标端图谱文件: {target_path}")
        return

    print("=" * 60)
    print("⚖️  CP2RS Phase 3: 指标评估裁决引擎已启动")
    print("=" * 60)

    # ---------------------------------------------------------
    # 指标一：宏观功能点对齐度 (Macro Alignment)
    # ---------------------------------------------------------
    report_name = f"{args.source.replace('_rpg.json', '')}_vs_{args.target.replace('_rpg.json', '')}_macro_alignment.json"
    report_path = os.path.join(REPORT_OUTPUT_DIR, report_name)
    
    evaluate_macro_alignment(source_path, target_path, report_path)

    # ---------------------------------------------------------
    # 指标二：微观函数对齐正确度 (预留插槽)
    # ---------------------------------------------------------
    # evaluate_micro_correctness(...)

if __name__ == "__main__":
    main()