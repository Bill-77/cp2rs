import os
import sys
import json
import argparse
from rpg_builder.llm_client import LLMClient
from phase3_evaluator.funnel_aligner import FunnelAligner
from phase3_evaluator.metric_calculator_3a import MetricCalculator3A

def check_file_exists(filepath: str) -> bool:
    """检查文件是否存在，并给予带颜色的错误提示"""
    if not os.path.exists(filepath):
        print(f"❌ 致命错误: 找不到必要的数据文件 -> {filepath}")
        return False
    return True

def main():
    # 1. 设置命令行参数解析
    parser = argparse.ArgumentParser(description="CP2RS Phase 3: 架构对齐与微观测试引擎")
    parser.add_argument("--src", type=str, required=True, help="源仓库的名称 (例如: cjson)")
    parser.add_argument("--tgt", type=str, required=True, help="目标仓库的名称 (例如: rust_json)")
    parser.add_argument("--model", type=str, default="deepseek-chat", help="指定调用的大模型，默认 deepseek-chat")
    
    args = parser.parse_args()
    
    print(f"🚀 CP2RS Phase 3 启动 | 正在评测: [{args.src}] ➡️  [{args.tgt}]")

    # 2. 自动构建动态路径
    base_parsed_dir = os.path.join("output", "parsed_repos")
    base_rpg_dir = os.path.join("output", "rpg_graphs")

    src_db_path = os.path.join(base_parsed_dir, f"{args.src}_parsed.json")
    tgt_db_path = os.path.join(base_parsed_dir, f"{args.tgt}_parsed.json")
    src_rpg_path = os.path.join(base_rpg_dir, f"{args.src}_rpg.json")
    tgt_rpg_path = os.path.join(base_rpg_dir, f"{args.tgt}_rpg.json")

    # 3. 严格的安全校验
    paths_to_check = [src_db_path, tgt_db_path, src_rpg_path, tgt_rpg_path]
    if not all(check_file_exists(p) for p in paths_to_check):
        print("\n💡 提示: 请确认 Phase 1 和 Phase 2 已正确生成了上述仓库的 schema 和 rpg 文件。")
        sys.exit(1)

    # 4. 初始化引擎
    try:
        llm_client = LLMClient(model=args.model)
        aligner = FunnelAligner(llm_client)
    except ValueError as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)

    # 5.1 执行 3A 对齐流水线
    print("\n" + "="*50)
    report = aligner.run_alignment(src_rpg_path, tgt_rpg_path, src_db_path, tgt_db_path)
    print("="*50)

    # 5.2 运行量化打分引擎
    calculator = MetricCalculator3A()
    report = calculator.calculate_scores(report, src_rpg_path, tgt_rpg_path, src_db_path, tgt_db_path)   
    print("="*50)

    # 6. 结果动态落盘
    output_dir = os.path.join("output", "eval_reports")
    os.makedirs(output_dir, exist_ok=True)
    
    # 文件名也会自动根据仓库名生成
    report_filename = f"3A_alignment_{args.src}_vs_{args.tgt}.json"
    report_path = os.path.join(output_dir, report_filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"\n✅ 3A 对齐报告已成功保存至: {report_path}")

if __name__ == "__main__":
    main()