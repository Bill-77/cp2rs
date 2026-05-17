import os
import sys
import json
import argparse
from rpg_builder.llm_client import LLMClient
from phase3_evaluator.funnel_aligner import FunnelAligner
from phase3_evaluator.metric_calculator_3a import MetricCalculator3A
from phase3_evaluator.static_analyzer import StaticAnalyzer
from phase3_evaluator.strategy_analyzer import StrategyAnalyzer

def check_file_exists(filepath: str) -> bool:
    """检查文件是否存在，并给予带颜色的错误提示"""
    if not os.path.exists(filepath):
        print(f"❌ 致命错误: 找不到必要的数据文件 -> {filepath}")
        return False
    return True

def run_evaluation_pipeline(src_name, tgt_name, src_rpg_path, tgt_rpg_path, src_db_path, tgt_db_path, llm_client, out_prefix, reuse_3a=False):
    """通用的评估流水线 (封装了 3A 和 3C)，支持复用已有 3A 结果"""
    print(f"\n🚀 启动评估子流水线: [{src_name}] ➡️  [{tgt_name}]")
    
    # 提前构造输出路径
    output_dir = os.path.join("output", "eval_reports")
    os.makedirs(output_dir, exist_ok=True)
    path_3a = os.path.join(output_dir, f"3A_alignment_{out_prefix}.json")
    path_3c = os.path.join(output_dir, f"3C_static_{out_prefix}.json")
    
    # ==========================================
    # 1 & 2. 3A 双重漏斗对齐与量化算分 (支持跳过)
    # ==========================================
    if reuse_3a and os.path.exists(path_3a):
        print(f"   -> ♻️ 检测到复用已有 3A 报告指令 --reuse-3a，直接复用: {path_3a}")
    else:
        if reuse_3a:
            print(f"   -> ⚠️ 未找到已有 3A 报告 ({path_3a})，将重新执行 3A 对齐...")

        # 1. 跑 3A 双重漏斗对齐    
        print("\n" + "="*50)
        aligner = FunnelAligner(llm_client)
        report_3a = aligner.run_alignment(src_rpg_path, tgt_rpg_path, src_db_path, tgt_db_path)
        
        # 2. 跑 3A 量化算分
        calculator = MetricCalculator3A()
        report_3a = calculator.calculate_scores(report_3a, src_rpg_path, tgt_rpg_path, src_db_path, tgt_db_path) 
        print("="*50)
        
        with open(path_3a, 'w', encoding='utf-8') as f:
            json.dump(report_3a, f, indent=2, ensure_ascii=False)
        print(f"✅ 3A 对齐报告已保存至: {path_3a}")

    # ==========================================
    # 3. 跑 3C 静态全仓分析
    # ==========================================
    static_analyzer = StaticAnalyzer()
    report_3c = static_analyzer.run_global_analysis(src_db_path, tgt_db_path)
    
    with open(path_3c, 'w', encoding='utf-8') as f:
        json.dump(report_3c, f, indent=2, ensure_ascii=False)
    print(f"✅ 3C 静态报告已保存至: {path_3c}")

    return path_3a, path_3c

def main():
    parser = argparse.ArgumentParser(description="CP2RS Phase 3: 架构对齐与微观测试引擎")
    parser.add_argument("--src", type=str, required=True, help="源仓库的名称 (例如: cjson)")
    parser.add_argument("--tgt", type=str, required=True, help="目标仓库的名称 (例如: rust_json)")
    parser.add_argument("--ans", type=str, required=False, help="人类专家 Answer Rust 仓库名 (提供此参数将触发场景二)")
    parser.add_argument("--model", type=str, default="deepseek-v4-flash", help="指定调用的大模型，默认使用 deepseek-v4-flash")
    parser.add_argument("--reuse-3a", action="store_true", help="跳过 3A 大模型对齐，直接读取并复用已有的 JSON 报告")
    args = parser.parse_args()

    # 路径构造辅助函数
    def get_paths(repo_name):
        db_path = os.path.join("output", "parsed_repos", f"{repo_name}_parsed.json")
        rpg_path = os.path.join("output", "rpg_graphs", f"{repo_name}_rpg.json")
        return rpg_path, db_path

    src_rpg_path, src_db_path = get_paths(args.src)
    tgt_rpg_path, tgt_db_path = get_paths(args.tgt)

    # 校验必要文件
    paths_to_check = [src_db_path, tgt_db_path, src_rpg_path, tgt_rpg_path]
    if args.ans:
        ans_rpg_path, ans_db_path = get_paths(args.ans)
        paths_to_check.extend([ans_db_path, ans_rpg_path])

    if not all(check_file_exists(p) for p in paths_to_check):
        print("\n💡 提示: 请确认 Phase 1 和 Phase 2 已正确生成了上述仓库的 schema 和 rpg 文件。")
        sys.exit(1)

    # 初始化大模型
    try:
        llm_client = LLMClient(model=args.model)
    except ValueError as e:
        print(f"\n❌ 初始化大模型失败: {e}")
        sys.exit(1)

    print("="*60)
    mode_text = "场景一 (无标杆仓库)" if not args.ans else f"场景二 (引入标杆仓库 [{args.ans}])"
    cache_text = "[♻️ 已开启 3A 缓存复用]" if args.reuse_3a else ""
    print(f"🛠️  运行模式: {mode_text} {cache_text}")
    print("="*60)

    # ---------------------------------------------------------
    # 任务 1: 执行 Source vs Target (基础评价)
    # ---------------------------------------------------------
    run_evaluation_pipeline(
        args.src, args.tgt, 
        src_rpg_path, tgt_rpg_path, 
        src_db_path, tgt_db_path, 
        llm_client, 
        f"{args.src}_vs_{args.tgt}",
        reuse_3a=args.reuse_3a
    )

    # ---------------------------------------------------------
    # 任务 2: 触发场景二 (Target vs Answer + 战略透视)
    # ---------------------------------------------------------
    if args.ans:
        # 将 Target 视作 '源'，Answer 视作 '目标' 跑复用流水线
        tgt_ans_3a_path, _ = run_evaluation_pipeline(
            args.tgt, args.ans, 
            tgt_rpg_path, ans_rpg_path, 
            tgt_db_path, ans_db_path, 
            llm_client, 
            f"{args.tgt}_vs_{args.ans}",
            reuse_3a=args.reuse_3a  # 同样支持复用 Target vs Answer 的 3A
        )
        
        # 激活战略透视报告引擎
        strategy_analyzer = StrategyAnalyzer(llm_client)
        strategy_report = strategy_analyzer.generate_strategy_report(tgt_ans_3a_path)
        
        output_dir = os.path.join("output", "eval_reports")
        strat_path = os.path.join(output_dir, f"3A_STRATEGY_{args.tgt}_vs_{args.ans}.json")
        with open(strat_path, "w", encoding="utf-8") as f:
            json.dump(strategy_report, f, indent=2, ensure_ascii=False)
            
        print(f"✅ 深度战略透视报告已保存至: {strat_path}")

    print("\n🎉 CP2RS Phase 3 指标评估执行完毕！")

if __name__ == "__main__":
    main()