import os
import sys
import json
import argparse
from rpg_builder.llm_client import LLMClient
from phase3_evaluator.funnel_aligner import FunnelAligner
from phase3_evaluator.metric_calculator_3a import MetricCalculator3A
from phase3_evaluator.static_analyzer import StaticAnalyzer
from phase3_evaluator.strategy_analyzer import StrategyAnalyzer

def normalize_output_suffix(output_suffix: str) -> str:
    """标准化报告文件后缀，避免命令行传参时纠结下划线。"""
    suffix = (output_suffix or "").strip()
    if suffix and not suffix.startswith("_"):
        suffix = f"_{suffix}"
    return suffix

def get_eval_report_paths(out_prefix: str, output_suffix: str = ""):
    output_dir = os.path.join("output", "eval_reports")
    suffix = normalize_output_suffix(output_suffix)
    path_3a = os.path.join(output_dir, f"3A_alignment_{out_prefix}{suffix}.json")
    path_3c = os.path.join(output_dir, f"3C_static_{out_prefix}{suffix}.json")
    return output_dir, path_3a, path_3c

def check_file_exists(filepath: str) -> bool:
    """检查文件是否存在，并给予带颜色的错误提示"""
    if not os.path.exists(filepath):
        print(f"❌ 致命错误: 找不到必要的数据文件 -> {filepath}")
        return False
    return True

def run_evaluation_pipeline(
    src_name,
    tgt_name,
    src_rpg_path,
    tgt_rpg_path,
    src_db_path,
    tgt_db_path,
    llm_client,
    out_prefix,
    phases,
    three_a_mode="run",
    output_suffix=""
):
    """通用的评估流水线，按命令行指定执行 3A/3C。"""
    print(f"\n🚀 启动评估子流水线: [{src_name}] ➡️  [{tgt_name}]")
    
    # 提前构造输出路径
    output_dir, path_3a, path_3c = get_eval_report_paths(out_prefix, output_suffix)
    os.makedirs(output_dir, exist_ok=True)
    
    # ==========================================
    # 1 & 2. 3A 双重漏斗对齐与量化算分
    # ==========================================
    if "3a" not in phases:
        print("   -> ⏭️  按参数跳过 3A 对齐与量化算分。")
    else:
        if three_a_mode in ("reuse", "require-cache") and os.path.exists(path_3a):
            print(f"   -> ♻️ 复用已有 3A 报告: {path_3a}")
            with open(path_3a, "r", encoding="utf-8") as f:
                report_3a = json.load(f)

            calculator = MetricCalculator3A()
            report_3a = calculator.calculate_scores(report_3a, src_rpg_path, tgt_rpg_path, src_db_path, tgt_db_path)
            with open(path_3a, 'w', encoding='utf-8') as f:
                json.dump(report_3a, f, indent=2, ensure_ascii=False)
            print(f"✅ 3A 缓存报告指标已按当前规则刷新: {path_3a}")
        elif three_a_mode == "require-cache":
            raise FileNotFoundError(f"按参数要求必须复用 3A 缓存，但未找到: {path_3a}")
        else:
            if three_a_mode == "reuse":
                print(f"   -> ⚠️ 未找到已有 3A 报告 ({path_3a})，将重新执行 3A 对齐...")
            if llm_client is None:
                raise ValueError("需要执行 3A 大模型对齐，但 llm_client 未初始化。")

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
    if "3c" not in phases:
        print("   -> ⏭️  按参数跳过 3C 全局静态指标统计。")
    else:
        static_analyzer = StaticAnalyzer()
        report_3c = static_analyzer.run_global_analysis(src_db_path, tgt_db_path)
        
        with open(path_3c, 'w', encoding='utf-8') as f:
            json.dump(report_3c, f, indent=2, ensure_ascii=False)
        print(f"✅ 3C 静态报告已保存至: {path_3c}")

    return path_3a, path_3c

def main():
    parser = argparse.ArgumentParser(description="CP2RS Phase 3: 架构对齐与静态指标引擎")
    parser.add_argument("--src", type=str, required=True, help="源仓库的名称 (例如: cjson)")
    parser.add_argument("--tgt", type=str, required=True, help="目标仓库的名称 (例如: rust_json)")
    parser.add_argument("--ans", type=str, required=False, help="人类专家 Answer Rust 仓库名 (提供此参数将触发场景二)")
    parser.add_argument("--model", type=str, default="deepseek-v4-flash", help="指定调用的大模型，默认使用 deepseek-v4-flash")
    parser.add_argument("--phases", nargs="+", choices=["3a", "3c"], default=["3a", "3c"],
                        help="指定本次执行哪些部分，例如: --phases 3c 或 --phases 3a 3c")
    parser.add_argument("--three-a-mode", choices=["run", "reuse", "require-cache"], default=None,
                        help="控制 3A 执行策略: run=强制重新调用大模型并覆盖报告; reuse=有缓存则复用、无缓存则重跑; require-cache=必须有缓存，否则失败")
    parser.add_argument("--reuse-3a", action="store_true", help="兼容旧参数，等价于 --three-a-mode reuse")
    parser.add_argument("--output-suffix", type=str, default="",
                        help="给输出报告文件名追加后缀，便于对比实验且不覆盖旧报告，例如: --output-suffix funnelfix")
    args = parser.parse_args()

    phases = set(args.phases)
    three_a_mode = args.three_a_mode or ("reuse" if args.reuse_3a else "run")

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

    # 仅在需要重新执行 3A 对齐时初始化大模型。
    def has_cached_3a(out_prefix):
        _, report_path, _ = get_eval_report_paths(out_prefix, args.output_suffix)
        return os.path.exists(report_path)

    needs_llm = False
    if "3a" in phases:
        if three_a_mode == "run":
            needs_llm = True
        elif three_a_mode == "reuse":
            needs_llm = not has_cached_3a(f"{args.src}_vs_{args.tgt}")
            if args.ans:
                needs_llm = needs_llm or not has_cached_3a(f"{args.tgt}_vs_{args.ans}")

    llm_client = None
    if needs_llm:
        try:
            llm_client = LLMClient(model=args.model)
        except ValueError as e:
            print(f"\n❌ 初始化大模型失败: {e}")
            sys.exit(1)
    else:
        print("♻️  本次不需要调用大模型，跳过 LLM 初始化。")

    print("="*60)
    mode_text = "场景一 (无标杆仓库)" if not args.ans else f"场景二 (引入标杆仓库 [{args.ans}])"
    print(f"🛠️  运行模式: {mode_text}")
    print(f"📌 执行阶段: {', '.join(sorted(phases))} | 3A策略: {three_a_mode} | 输出后缀: {normalize_output_suffix(args.output_suffix) or '(无)'}")
    print("="*60)

    try:
        # ---------------------------------------------------------
        # 任务 1: 执行 Source vs Target (基础评价)
        # ---------------------------------------------------------
        run_evaluation_pipeline(
            args.src, args.tgt, 
            src_rpg_path, tgt_rpg_path, 
            src_db_path, tgt_db_path, 
            llm_client, 
            f"{args.src}_vs_{args.tgt}",
            phases=phases,
            three_a_mode=three_a_mode,
            output_suffix=args.output_suffix
        )

        # ---------------------------------------------------------
        # 任务 2: 触发场景二 (Target vs Answer + 战略透视)
        # ---------------------------------------------------------
        if args.ans:
            tgt_ans_3a_path, _ = run_evaluation_pipeline(
                args.tgt, args.ans, 
                tgt_rpg_path, ans_rpg_path, 
                tgt_db_path, ans_db_path, 
                llm_client, 
                f"{args.tgt}_vs_{args.ans}",
                phases=phases,
                three_a_mode=three_a_mode,
                output_suffix=args.output_suffix
            )
            
            # 激活战略透视报告引擎
            print("   -> ⚠️ [调试模式] 已暂停生成深度战略透视报告 (Strategy Report)。")
            # strategy_analyzer = StrategyAnalyzer(llm_client)
            # strategy_report = strategy_analyzer.generate_strategy_report(tgt_ans_3a_path)
            
            # output_dir = os.path.join("output", "eval_reports")
            # strat_path = os.path.join(output_dir, f"3A_STRATEGY_{args.tgt}_vs_{args.ans}.json")
            # with open(strat_path, "w", encoding="utf-8") as f:
            #     json.dump(strategy_report, f, indent=2, ensure_ascii=False)
                
            # print(f"✅ 深度战略透视报告已保存至: {strat_path}")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ Phase 3 执行失败: {e}")
        sys.exit(1)

    print("\n🎉 CP2RS Phase 3 指标评估执行完毕！")

if __name__ == "__main__":
    main()
