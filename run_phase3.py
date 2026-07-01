import os
import sys
import json
import argparse
from rpg_builder.llm_client import LLMClient
from phase3_evaluator.funnel_aligner import FunnelAligner
from phase3_evaluator.metric_calculator_3a import MetricCalculator3A
from phase3_evaluator.static_analyzer import StaticAnalyzer
from phase3_evaluator.strategy_analyzer import StrategyAnalyzer
from phase3_evaluator.trace_replay_3b import TraceReplay3B

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

def get_eval_report_path_3b(out_prefix: str, output_suffix: str = ""):
    output_dir = os.path.join("output", "eval_reports")
    suffix = normalize_output_suffix(output_suffix)
    return os.path.join(output_dir, f"3B_correctness_{out_prefix}{suffix}.json")

def get_phase3b_artifact_dir(out_prefix: str, output_suffix: str = ""):
    suffix = normalize_output_suffix(output_suffix)
    return os.path.join("output", "phase3_3b", f"{out_prefix}{suffix}")

def find_repo_path(repo_name: str):
    """按仓库名在 Phase 1 默认输入目录中查找原始源码仓库。"""
    base_dirs = ["data/cc_repos", "data/rust_repos"]
    for base_dir in base_dirs:
        exact_path = os.path.join(base_dir, repo_name)
        if os.path.isdir(exact_path):
            return exact_path

    repo_name_lower = repo_name.lower()
    for base_dir in base_dirs:
        if not os.path.isdir(base_dir):
            continue
        for child in os.listdir(base_dir):
            child_path = os.path.join(base_dir, child)
            if os.path.isdir(child_path) and child.lower() == repo_name_lower:
                return child_path
    return None

def resolve_path(default_path: str, override_path: str = None) -> str:
    """命令行显式路径优先，否则使用默认路径。"""
    return override_path or default_path

def has_phase3b_adapter(src_name: str, tgt_name: str, explicit_adapter: str = None) -> bool:
    """判断 3B auto 模式是否能复用已有 adapter。"""
    if explicit_adapter:
        return os.path.exists(explicit_adapter)
    return TraceReplay3B.has_reusable_default_adapter(src_name, tgt_name)

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
    three_b_mode="run",
    three_b_layer="public",
    three_b_adapter=None,
    three_b_adapter_mode="existing",
    three_b_synthesis_attempts=3,
    three_b_replay_repair_attempts=3,
    three_b_completion_iterations=0,
    three_b_completion_batch_size=10,
    three_b_keep_debug_artifacts=False,
    three_b_alignment_report=None,
    src_repo_path_override=None,
    tgt_repo_path_override=None,
    output_suffix=""
):
    """通用的评估流水线，按命令行指定执行 3A/3B/3C。"""
    print(f"\n🚀 启动评估子流水线: [{src_name}] ➡️  [{tgt_name}]")
    
    # 提前构造输出路径
    output_dir, path_3a, path_3c = get_eval_report_paths(out_prefix, output_suffix)
    path_3b = get_eval_report_path_3b(out_prefix, output_suffix)
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
    # 2.5. 跑 3B Trace Replay Public-First
    # ==========================================
    if "3b" not in phases:
        print("   -> ⏭️  按参数跳过 3B Trace Replay 正确性测试。")
    else:
        alignment_path_3b = three_b_alignment_report or path_3a
        if not os.path.exists(alignment_path_3b) and "3a" not in phases and output_suffix:
            _, base_path_3a, _ = get_eval_report_paths(out_prefix, "")
            if os.path.exists(base_path_3a):
                alignment_path_3b = base_path_3a
                print(f"   -> ♻️ 3B 未找到同后缀 3A 报告，改用基础 3A 报告: {alignment_path_3b}")
        if not os.path.exists(alignment_path_3b):
            raise FileNotFoundError(f"3B 需要已有 3A 对齐报告，请先运行 3A 或使用正确后缀: {path_3a}")

        src_repo_path = src_repo_path_override or find_repo_path(src_name)
        tgt_repo_path = tgt_repo_path_override or find_repo_path(tgt_name)
        artifacts_dir = get_phase3b_artifact_dir(out_prefix, output_suffix)

        evaluator_3b = TraceReplay3B(
            src_name=src_name,
            tgt_name=tgt_name,
            src_repo_path=src_repo_path,
            tgt_repo_path=tgt_repo_path,
            alignment_report_path=alignment_path_3b,
            src_db_path=src_db_path,
            tgt_db_path=tgt_db_path,
            adapter_path=three_b_adapter,
            adapter_mode=three_b_adapter_mode,
            synthesis_attempts=three_b_synthesis_attempts,
            replay_repair_attempts=three_b_replay_repair_attempts,
            completion_iterations=three_b_completion_iterations,
            completion_batch_size=three_b_completion_batch_size,
            keep_debug_artifacts=three_b_keep_debug_artifacts,
            llm_client=llm_client,
        )
        report_3b = evaluator_3b.run(
            mode=three_b_mode,
            layer=three_b_layer,
            artifacts_dir=artifacts_dir,
        )

        with open(path_3b, 'w', encoding='utf-8') as f:
            json.dump(report_3b, f, indent=2, ensure_ascii=False)
        print(f"✅ 3B Trace Replay 报告已保存至: {path_3b}")
        print(f"   -> 3B 中间产物目录: {artifacts_dir}")

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

    return path_3a, path_3b, path_3c

def main():
    parser = argparse.ArgumentParser(description="CP2RS Phase 3: 架构对齐与静态指标引擎")
    parser.add_argument("--src", type=str, required=True, help="源仓库的名称 (例如: cjson)")
    parser.add_argument("--tgt", type=str, required=True, help="目标仓库的名称 (例如: rust_json)")
    parser.add_argument("--ans", type=str, required=False, help="人类专家 Answer Rust 仓库名 (提供此参数将触发场景二)")
    parser.add_argument("--model", type=str, default="deepseek-v4-flash", help="指定调用的大模型，默认使用 deepseek-v4-flash")
    parser.add_argument("--phases", nargs="+", choices=["3a", "3b", "3c"], default=["3a", "3c"],
                        help="指定本次执行哪些部分，例如: --phases 3b 或 --phases 3a 3b 3c")
    parser.add_argument("--three-a-mode", choices=["run", "reuse", "require-cache"], default=None,
                        help="控制 3A 执行策略: run=强制重新调用大模型并覆盖报告; reuse=有缓存则复用、无缓存则重跑; require-cache=必须有缓存，否则失败")
    parser.add_argument("--three-b-mode", choices=["inventory", "record", "replay", "run"], default="run",
                        help="控制 3B 执行策略: inventory=只发现测试; record=生成 trace; replay/run=生成并执行 target replay")
    parser.add_argument("--three-b-layer", choices=["public", "function", "both"], default="public",
                        help="控制 3B 粒度: public=默认只测公开行为; function/both=保留函数边界诊断入口")
    parser.add_argument("--three-b-adapter", type=str, default=None,
                        help="指定 3B adapter JSON；不指定时会尝试内置 adapter 或报告 adapter_missing")
    parser.add_argument("--three-b-adapter-mode", choices=["existing", "auto", "synthesize", "prompt-only"], default="existing",
                        help="控制 3B adapter 来源: existing=使用已有/默认adapter; auto=有adapter则复用、否则LLM生成; synthesize=显式调用LLM生成; prompt-only=只生成LLM上下文与提示词")
    parser.add_argument("--three-b-generation-max-attempts", "--three-b-synthesis-attempts",
                        dest="three_b_synthesis_attempts", type=int, default=3,
                        help="每个 eligible behavior case 的 adapter 生成最大尝试次数，默认 3")
    parser.add_argument("--three-b-replay-repair-attempts", type=int, default=3,
                        help="target replay 发生编译/运行基础设施失败时的修复次数，默认 3")
    parser.add_argument(
        "--three-b-generation-iterations", "--three-b-completion-iterations", "--three-b-agent-iterations",
        dest="three_b_completion_iterations", type=int, default=0,
        help="3B adapter case 生成轮次；0=按每个 case 最大尝试次数自动计算（默认），正数=硬上限，-1=禁用",
    )
    parser.add_argument(
        "--three-b-generation-batch-size", "--three-b-completion-batch-size", "--three-b-agent-batch-size",
        dest="three_b_completion_batch_size", type=int, default=10,
        help="3B 每批生成 adapter 的 eligible source behavior case 数，默认 10；旧参数名仍兼容",
    )
    parser.add_argument("--three-b-keep-debug-artifacts", action="store_true",
                        help="保留 3B LLM 生成/修复过程中的 prompt、raw response、attempt adapter 与运行 worktree；默认不生成这些调试产物，只保留正式产物")
    parser.add_argument("--three-b-alignment-report", type=str, default=None,
                        help="显式指定 3B 使用的 3A 对齐报告路径；用于非默认目录/任意仓库输入")
    parser.add_argument("--src-repo-path", type=str, default=None,
                        help="显式指定 src 原始仓库路径；不指定时按仓库名在 data/cc_repos 与 data/rust_repos 中查找")
    parser.add_argument("--tgt-repo-path", type=str, default=None,
                        help="显式指定 tgt 原始仓库路径；不指定时按仓库名在 data/cc_repos 与 data/rust_repos 中查找")
    parser.add_argument("--ans-repo-path", type=str, default=None,
                        help="显式指定 ans 原始仓库路径；仅场景二使用")
    parser.add_argument("--src-db-path", type=str, default=None,
                        help="显式指定 src parsed DB 路径；不指定时使用 output/parsed_repos/{src}_parsed.json")
    parser.add_argument("--tgt-db-path", type=str, default=None,
                        help="显式指定 tgt parsed DB 路径；不指定时使用 output/parsed_repos/{tgt}_parsed.json")
    parser.add_argument("--ans-db-path", type=str, default=None,
                        help="显式指定 ans parsed DB 路径；仅场景二使用")
    parser.add_argument("--src-rpg-path", type=str, default=None,
                        help="显式指定 src RPG 路径；仅执行 3A 时需要")
    parser.add_argument("--tgt-rpg-path", type=str, default=None,
                        help="显式指定 tgt RPG 路径；仅执行 3A 时需要")
    parser.add_argument("--ans-rpg-path", type=str, default=None,
                        help="显式指定 ans RPG 路径；仅场景二执行 3A 时需要")
    parser.add_argument("--reuse-3a", action="store_true", help="兼容旧参数，等价于 --three-a-mode reuse")
    parser.add_argument("--output-suffix", type=str, default="",
                        help="给输出报告文件名追加后缀，便于对比实验且不覆盖旧报告，例如: --output-suffix funnelfix")
    args = parser.parse_args()

    phases = set(args.phases)
    three_a_mode = args.three_a_mode or ("reuse" if args.reuse_3a else "run")

    # 路径构造辅助函数
    def get_paths(repo_name, db_override=None, rpg_override=None):
        db_path = resolve_path(os.path.join("output", "parsed_repos", f"{repo_name}_parsed.json"), db_override)
        rpg_path = resolve_path(os.path.join("output", "rpg_graphs", f"{repo_name}_rpg.json"), rpg_override)
        return rpg_path, db_path

    src_rpg_path, src_db_path = get_paths(args.src, args.src_db_path, args.src_rpg_path)
    tgt_rpg_path, tgt_db_path = get_paths(args.tgt, args.tgt_db_path, args.tgt_rpg_path)

    # 校验必要文件
    paths_to_check = []
    if phases.intersection({"3a", "3b", "3c"}):
        paths_to_check.extend([src_db_path, tgt_db_path])
    if "3a" in phases:
        paths_to_check.extend([src_rpg_path, tgt_rpg_path])
    if args.ans:
        ans_rpg_path, ans_db_path = get_paths(args.ans, args.ans_db_path, args.ans_rpg_path)
        paths_to_check.append(ans_db_path)
        if "3a" in phases:
            paths_to_check.append(ans_rpg_path)

    if not all(check_file_exists(p) for p in paths_to_check):
        print("\n💡 提示: 请确认 Phase 1 和 Phase 2 已正确生成了上述仓库的 schema 和 rpg 文件。")
        sys.exit(1)

    # 仅在当前阶段确实可能调用大模型时初始化。
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
    if "3b" in phases and args.three_b_mode != "inventory" and args.three_b_adapter_mode != "prompt-only":
        if args.three_b_adapter_mode == "synthesize":
            needs_llm = True
        elif args.three_b_adapter_mode == "auto":
            needs_llm = not has_phase3b_adapter(args.src, args.tgt, args.three_b_adapter)
            if args.ans:
                needs_llm = needs_llm or not has_phase3b_adapter(args.tgt, args.ans, args.three_b_adapter)
        if args.three_b_mode in {"replay", "run"} and args.three_b_replay_repair_attempts > 0:
            needs_llm = True

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
    completion_iteration_text = "auto" if args.three_b_completion_iterations == 0 else ("disabled" if args.three_b_completion_iterations < 0 else str(args.three_b_completion_iterations))
    print(f"🛠️  运行模式: {mode_text}")
    print(f"📌 执行阶段: {', '.join(sorted(phases))} | 3A策略: {three_a_mode} | 3B策略: {args.three_b_mode}/{args.three_b_layer}/{args.three_b_adapter_mode} | 3B每case生成上限: {args.three_b_synthesis_attempts} | 3B replay修复: {args.three_b_replay_repair_attempts} | 3B生成轮次: {completion_iteration_text} | 3B生成批量: {args.three_b_completion_batch_size} | 3B调试产物: {'保留' if args.three_b_keep_debug_artifacts else '不生成'} | 输出后缀: {normalize_output_suffix(args.output_suffix) or '(无)'}")
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
            three_b_mode=args.three_b_mode,
            three_b_layer=args.three_b_layer,
            three_b_adapter=args.three_b_adapter,
            three_b_adapter_mode=args.three_b_adapter_mode,
            three_b_synthesis_attempts=args.three_b_synthesis_attempts,
            three_b_replay_repair_attempts=args.three_b_replay_repair_attempts,
            three_b_completion_iterations=args.three_b_completion_iterations,
            three_b_completion_batch_size=args.three_b_completion_batch_size,
            three_b_keep_debug_artifacts=args.three_b_keep_debug_artifacts,
            three_b_alignment_report=args.three_b_alignment_report,
            src_repo_path_override=args.src_repo_path,
            tgt_repo_path_override=args.tgt_repo_path,
            output_suffix=args.output_suffix
        )

        # ---------------------------------------------------------
        # 任务 2: 触发场景二 (Target vs Answer + 战略透视)
        # ---------------------------------------------------------
        if args.ans:
            tgt_ans_3a_path, _, _ = run_evaluation_pipeline(
                args.tgt, args.ans, 
                tgt_rpg_path, ans_rpg_path, 
                tgt_db_path, ans_db_path, 
                llm_client, 
                f"{args.tgt}_vs_{args.ans}",
                phases=phases,
                three_a_mode=three_a_mode,
                three_b_mode=args.three_b_mode,
                three_b_layer=args.three_b_layer,
                three_b_adapter=args.three_b_adapter,
                three_b_adapter_mode=args.three_b_adapter_mode,
                three_b_synthesis_attempts=args.three_b_synthesis_attempts,
                three_b_replay_repair_attempts=args.three_b_replay_repair_attempts,
                three_b_completion_iterations=args.three_b_completion_iterations,
                three_b_completion_batch_size=args.three_b_completion_batch_size,
                three_b_keep_debug_artifacts=args.three_b_keep_debug_artifacts,
                src_repo_path_override=args.tgt_repo_path,
                tgt_repo_path_override=args.ans_repo_path,
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
