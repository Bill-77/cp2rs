import os
import argparse
from phase3_evaluator.macro_alignment import evaluate_macro_alignment
from phase3_evaluator.micro_correctness import evaluate_micro_correctness

# 配置路径
RPG_OUTPUT_DIR = "output/rpg_graphs"
REPORT_OUTPUT_DIR = "output/evaluation_reports"
PARSED_OUTPUT_DIR = "output/parsed_repos"

def main():
    parser = argparse.ArgumentParser(description="CP2RS Phase 3: 跨语言等价性评测总控")
    
    # 基础参数 (适用于所有场景)
    parser.add_argument("--source", type=str, required=True, help="源仓库的 RPG (如: cJSON_rpg.json)")
    parser.add_argument("--target", type=str, required=True, help="翻译结果的 RPG (如: trans_rpg.json)")
    
    # 标杆测试专属参数 (可选)
    parser.add_argument("--answer_rpg", type=str, help="答案仓库的 RPG (如: json-rust_rpg.json)")
    parser.add_argument("--answer_repo_dir", type=str, help="答案仓库的物理根目录 (如: data/rust_repos/json-rust)")
    parser.add_argument("--target_schema", type=str, help="翻译结果的阶段一 Schema (如: trans_parsed.json)")
    parser.add_argument("--target_repo_dir", type=str, help="翻译结果的物理根目录，用于运行 cargo test")
    
    args = parser.parse_args()

    source_path = os.path.join(RPG_OUTPUT_DIR, args.source)
    target_path = os.path.join(RPG_OUTPUT_DIR, args.target)

    if not os.path.exists(source_path) or not os.path.exists(target_path):
        print("❌ 找不到源端或目标端的 RPG 图谱文件！")
        return

    print("=" * 60)
    print("⚖️  CP2RS Phase 3: 指标评估裁决引擎已启动")
    print("=" * 60)

    # ---------------------------------------------------------
    # 指标一 宏观功能点对齐度 (Source VS Target)
    # ---------------------------------------------------------
    report_name_1 = f"{args.source.replace('_rpg.json', '')}_vs_{args.target.replace('_rpg.json', '')}_macro_alignment.json"
    report_path_1 = os.path.join(REPORT_OUTPUT_DIR, report_name_1)
    
    print("\n[1/2] 正在评估翻译仓库与源仓库的宏观架构对齐度...")
    evaluate_macro_alignment(source_path, target_path, report_path_1)

    # ---------------------------------------------------------
    # 检测是否进入标杆测试模式
    # ---------------------------------------------------------
    if not args.answer_rpg:
        print("\n🏁 检测到未传入答案仓库参数。以非标杆模式运行，Phase 3 评估结束。")
        return

    # 校验标杆测试所需的完整参数
    if not all([args.answer_repo_dir, args.target_schema, args.target_repo_dir]):
        print("❌ 标杆模式下，缺少必要的路径参数 (--answer_repo_dir, --target_schema, --target_repo_dir)")
        return

    answer_rpg_path = os.path.join(RPG_OUTPUT_DIR, args.answer_rpg)
    target_schema_path = os.path.join(PARSED_OUTPUT_DIR, args.target_schema)

    # ---------------------------------------------------------
    # 获取 Rust 🆚 Rust 的映射考卷 (Target VS Answer)
    # ---------------------------------------------------------
    report_name_2 = f"{args.target.replace('_rpg.json', '')}_vs_{args.answer_rpg.replace('_rpg.json', '')}_macro_alignment.json"
    report_path_2 = os.path.join(REPORT_OUTPUT_DIR, report_name_2)
    
    print("\n[2/2] 标杆模式开启！正在获取翻译仓库与答案仓库的底层映射...")
    # 复用 3A 的 Prompt，直接让两个 Rust 仓库碰一碰，找到目标函数和答案函数的对应关系
    evaluate_macro_alignment(target_path, answer_rpg_path, report_path_2)

    # ---------------------------------------------------------
    # 指标二 微观函数正确度 (沙盒处决)
    # ---------------------------------------------------------
    print("\n🚀 正在启动微观函数沙盒测试...")
    evaluate_micro_correctness(
        target_vs_answer_report=report_path_2,
        answer_repo_dir=args.answer_repo_dir,
        target_schema_path=target_schema_path,
        target_repo_dir=args.target_repo_dir
    )

if __name__ == "__main__":
    main()