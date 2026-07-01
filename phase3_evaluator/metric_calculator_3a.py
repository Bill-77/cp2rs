import json
from .function_uid import is_real_function_definition, iter_function_records
from .rpg_scope import collect_root_functions

class MetricCalculator3A:
    """
    CP2RS Phase 3A: 量化打分引擎
    纯代码计算硬核指标，剥离大模型的主观性，支持完全复现。
    以宏观模块覆盖率和微观函数覆盖率为核心驱动指标，包含架构碎片化指数、微观对齐置信度、接口膨胀率、孤儿函数率、交并比(IoU)、代码行数(LOC)膨胀率以及 Unsafe 质量探针。
    """
    def __init__(self):
        pass

    def _split_target_uuids(self, tgt_uuid: str) -> list:
        """拆分模型输出的 Target UUID，支持一个 Source 对应多个 Target。"""
        if not tgt_uuid:
            return []
        return [item.strip() for item in str(tgt_uuid).split(",") if item.strip()]

    def _is_real_function_definition(self, func: dict) -> bool:
        return is_real_function_definition(func)

    def _extract_unique_functions(self, file_path: str, file_data: dict) -> list:
        """核心修复：通过动态构建 UUID，彻底消除 functions 与 standalone_functions 的重复计数"""
        unique_funcs = {}
        
        for uid, func in iter_function_records(file_path, file_data, definitions_only=True):
            unique_funcs[uid] = func
                    
        return list(unique_funcs.values())

    def _dedupe_aligned_functions(self, funcs: list) -> list:
        deduped = []
        seen = set()
        for func in funcs or []:
            if not isinstance(func, dict):
                continue
            src_uuid = str(func.get("src_uuid", "")).strip()
            tgt_uuid = ",".join(self._split_target_uuids(func.get("tgt_uuid", "")))
            if not src_uuid or not tgt_uuid:
                continue
            key = (src_uuid, tgt_uuid)
            if key in seen:
                continue
            seen.add(key)
            func["src_uuid"] = src_uuid
            func["tgt_uuid"] = tgt_uuid
            deduped.append(func)
        return deduped

    def _extract_module_statistics(self, root_ids_str, rpg, parsed_db, is_target=False) -> dict:
        """
        全能特征提取器：返回函数总量、代码总行数(LOC)、Unsafe函数数量
        """
        stats = {"total_funcs": 0, "total_loc": 0, "unsafe_funcs": 0}
        if not root_ids_str: 
            return stats
            
        for _uid, func in collect_root_functions(root_ids_str, rpg, parsed_db, definitions_only=True):
            body = func.get("body", "")
            stats["total_funcs"] += 1
            stats["total_loc"] += len(body.splitlines())

            if is_target:
                signature = func.get("signature", "")
                if "unsafe " in signature or "unsafe {" in body or "unsafe{" in body:
                    stats["unsafe_funcs"] += 1
                                        
        return stats

    def calculate_scores(self, alignment_report: dict, src_rpg_path: str, tgt_rpg_path: str, src_db_path: str, tgt_db_path: str) -> dict:
        """
        计算并注入 3A 核心量化指标
        """
        print("📊 [Metric 3A] 正在深度扫描源码，计算交并比(IoU)、LOC膨胀率与 Unsafe 探针...")
        
        with open(src_rpg_path, 'r', encoding='utf-8') as f: src_rpg = json.load(f)
        with open(tgt_rpg_path, 'r', encoding='utf-8') as f: tgt_rpg = json.load(f)
        with open(src_db_path, 'r', encoding='utf-8') as f: src_db = json.load(f)
        with open(tgt_db_path, 'r', encoding='utf-8') as f: tgt_db = json.load(f)
        
       # 1. 建立全量 Root 节点语义描述字典 (合并 RPG 中 semantic_name 和 description)
        def get_desc(node):
            name = node.get('semantic_name', '')
            desc = node.get('description', '')
            if name and desc:
                return f"{name}: {desc}"
            return name or desc or "无描述"

        src_roots_info = {n['id']: get_desc(n) for n in src_rpg["nodes"].get("root_nodes", [])}
        tgt_roots_info = {n['id']: get_desc(n) for n in tgt_rpg["nodes"].get("root_nodes", [])}

        src_total_roots = len(src_roots_info)
        tgt_total_roots = len(tgt_roots_info)

        aligned_src_roots = set()
        aligned_tgt_roots = set()
        total_aligned_funcs = 0
        high_confidence_funcs = 0
        total_src_funcs, total_tgt_funcs = 0, 0
        total_src_loc, total_tgt_loc = 0, 0
        total_unsafe_funcs = 0
        unique_aligned_src_funcs = set()
        unique_aligned_tgt_funcs = set()

        # 2. 遍历已对齐模块并注入语义描述
        original_aligned_modules = alignment_report.get("aligned_modules", [])
        ordered_aligned_modules = []
        
        for mod in original_aligned_modules:
            src_ids = [s.strip() for s in mod["src_module"].split(",") if s.strip()]
            tgt_ids = [t.strip() for t in mod["tgt_module"].split(",") if t.strip()]
            
            aligned_src_roots.update(src_ids)
            aligned_tgt_roots.update(tgt_ids)
            
            # 提取对应的语义描述
            src_desc = "\n".join([f"[{sid}] {src_roots_info.get(sid, '无描述')}" for sid in src_ids])
            tgt_desc = "\n".join([f"[{tid}] {tgt_roots_info.get(tid, '无描述')}" for tid in tgt_ids])
            
            # 🛡️ 防御 NoneType 陷阱
            funcs = mod.get("aligned_functions")
            if funcs is None:
                funcs = []
            funcs = self._dedupe_aligned_functions(funcs)
                
            total_aligned_funcs += len(funcs)
            high_confidence_funcs += sum(1 for f in funcs if f.get("confidence", "").upper() == "HIGH")
            for func in funcs:
                src_uuid = func.get("src_uuid")
                if src_uuid:
                    unique_aligned_src_funcs.add(src_uuid)
                unique_aligned_tgt_funcs.update(self._split_target_uuids(func.get("tgt_uuid", "")))
            
            # 按要求的顺序重建字典
            ordered_mod = {
                "src_module": mod["src_module"],
                "src_module_description": src_desc,
                "tgt_module": mod["tgt_module"],
                "tgt_module_description": tgt_desc,
                "justification": mod.get("justification", ""),
                "aligned_functions": funcs
            }
            initial_tgt_module = mod.get("tgt_macro_initial_module") or mod.get("tgt_macro_module")
            completion = mod.get("macro_mapping_completion")
            if completion is None:
                completion = mod.get("target_scope_expansion")
            if initial_tgt_module:
                ordered_mod["tgt_macro_initial_module"] = initial_tgt_module
            if completion:
                ordered_mod["macro_mapping_completion"] = completion
            ordered_aligned_modules.append(ordered_mod)

        # 替换为排好序的新数组
        alignment_report["aligned_modules"] = ordered_aligned_modules

        # 统计口径必须按去重 Root 计算。3A 的微观候选范围可能为了处理
        # Rust public/facade/core-method 承载而重复包含同一个 target root，
        # 重复累加会夸大 target 函数总量与 LOC。
        src_stats = self._extract_module_statistics(",".join(sorted(aligned_src_roots)), src_rpg, src_db, is_target=False)
        tgt_stats = self._extract_module_statistics(",".join(sorted(aligned_tgt_roots)), tgt_rpg, tgt_db, is_target=True)
        total_src_funcs = src_stats["total_funcs"]
        total_src_loc = src_stats["total_loc"]
        total_tgt_funcs = tgt_stats["total_funcs"]
        total_tgt_loc = tgt_stats["total_loc"]
        total_unsafe_funcs = tgt_stats["unsafe_funcs"]
        
        # 3. 探查并组装未对齐模块 (Unaligned Modules)
        unaligned_src = [
            {"module_id": sid, "module_description": desc} 
            for sid, desc in src_roots_info.items() if sid not in aligned_src_roots
        ]
        unaligned_tgt = [
            {"module_id": tid, "module_description": desc} 
            for tid, desc in tgt_roots_info.items() if tid not in aligned_tgt_roots
        ]
        
        alignment_report["unaligned_modules"] = {
            "source_unaligned": unaligned_src,
            "target_unaligned": unaligned_tgt
        }

        # 4. 计算指标
        # 🥇 核心评分组件 (Macro & Micro)
        unique_aligned_src_count = len(unique_aligned_src_funcs)
        unique_aligned_tgt_count = len(unique_aligned_tgt_funcs)
        macro_coverage = len(aligned_src_roots) / src_total_roots if src_total_roots > 0 else 0
        micro_coverage = total_aligned_funcs / total_src_funcs if total_src_funcs > 0 else 0
        source_unique_coverage = unique_aligned_src_count / total_src_funcs if total_src_funcs > 0 else 0
        macro_score = (macro_coverage * 70) + (micro_coverage * 30)

        # 🥈 深度透视参考指标
        # 1. 架构碎片化指数
        fragmentation_index = len(aligned_tgt_roots) / len(aligned_src_roots) if len(aligned_src_roots) > 0 else 0
        
        # 2. 功能重合度 (Jaccard Index / IoU) 
        union_funcs = (total_src_funcs + total_tgt_funcs) - total_aligned_funcs
        functional_overlap_ratio = total_aligned_funcs / union_funcs if union_funcs > 0 else 0
        unique_union_funcs = (total_src_funcs + total_tgt_funcs) - min(unique_aligned_src_count, unique_aligned_tgt_count)
        unique_functional_overlap_ratio = min(unique_aligned_src_count, unique_aligned_tgt_count) / unique_union_funcs if unique_union_funcs > 0 else 0
        
        # 3. 体积膨胀率 (API 个数 vs LOC 行数)
        api_bloat_ratio = total_tgt_funcs / total_src_funcs if total_src_funcs > 0 else 0
        loc_bloat_ratio = total_tgt_loc / total_src_loc if total_src_loc > 0 else 0
        
        # 4. 孤儿与原生率
        source_orphan_count = total_src_funcs - unique_aligned_src_count
        target_native_count = total_tgt_funcs - unique_aligned_tgt_count
        source_orphan_rate = source_orphan_count / total_src_funcs if total_src_funcs > 0 else 0
        target_native_rate = target_native_count / total_tgt_funcs if total_tgt_funcs > 0 else 0
        target_unique_participation_rate = unique_aligned_tgt_count / total_tgt_funcs if total_tgt_funcs > 0 else 0
        mapping_compression_ratio = unique_aligned_src_count / unique_aligned_tgt_count if unique_aligned_tgt_count > 0 else 0
        target_reuse_factor = total_aligned_funcs / unique_aligned_tgt_count if unique_aligned_tgt_count > 0 else 0
        
        # 5. 质量指标 (Unsafe 率 & 置信度)
        unsafe_rate = total_unsafe_funcs / total_tgt_funcs if total_tgt_funcs > 0 else 0
        confidence_rate = high_confidence_funcs / total_aligned_funcs if total_aligned_funcs > 0 else 0

        # 5. 组装量化计分板
        metrics = {
            "atomic_base_data": {
                "total_source_modules": f"{src_total_roots} - Source 仓库的宏观模块(Root)总数",
                "aligned_source_modules": f"{len(aligned_src_roots)} - 成功在 Target 中找到对齐映射的 Source 模块数",
                "total_target_modules": f"{tgt_total_roots} - Target 仓库的宏观模块(Root)总数",
                "aligned_target_modules": f"{len(aligned_tgt_roots)} - 实际参与了架构对齐的 Target 模块数",
                "total_source_functions": f"{total_src_funcs} - Source 对齐模块下包含的真实函数总量",
                "total_target_functions": f"{total_tgt_funcs} - Target 对齐模块下包含的真实函数总量",
                "aligned_function_pairs": f"{total_aligned_funcs} - 通过微观校验，成功对齐的等价函数对数量",
                "unique_aligned_source_functions": f"{unique_aligned_src_count} - 去重后的已对齐 Source 函数量（按 src_uuid 去重）",
                "unique_aligned_target_functions": f"{unique_aligned_tgt_count} - 去重后的参与对齐 Target 函数量（按 tgt_uuid 去重，支持逗号分隔的一对多映射）",
                "union_functions": f"{union_funcs} - 两个仓库对齐模块下函数的去重并集总数",
                "unique_union_functions": f"{unique_union_funcs} - 基于去重函数参与量估算的 Source/Target 函数并集总数",
                "total_source_loc": f"{total_src_loc} - Source 对齐模块的总代码行数 (Lines of Code)",
                "total_target_loc": f"{total_tgt_loc} - Target 对齐模块的总代码行数 (Lines of Code)",
                "source_orphan_functions": f"{source_orphan_count} - Source 中未找到 Target 对应的孤儿函数量（基于 unique_aligned_source_functions）",
                "target_native_functions": f"{target_native_count} - Target 中无 Source 对应的原生函数量（基于 unique_aligned_target_functions）",
                "target_unsafe_functions": f"{total_unsafe_funcs} - Target 核心模块中带有 unsafe 标记或代码块的函数量",
                "high_confidence_alignments": f"{high_confidence_funcs} - 被大模型评估为 High 确信度的微观对齐函数量"
            },
            "derived_ratio_metrics": {
                "source_macro_coverage_rate": f"{macro_coverage * 100:.2f}% ( {len(aligned_src_roots)} / {src_total_roots} ) - 对齐的 Source 核心模块数 / Source 仓库总模块数",
                "source_micro_coverage_rate": f"{micro_coverage * 100:.2f}% ( {total_aligned_funcs} / {total_src_funcs} ) - 成功对齐的函数对数量 / Source 核心模块下的函数总量",
                "source_unique_micro_coverage_rate": f"{source_unique_coverage * 100:.2f}% ( {unique_aligned_src_count} / {total_src_funcs} ) - 去重后的已对齐 Source 函数量 / Source 核心模块下的函数总量",
                "target_unique_participation_rate": f"{target_unique_participation_rate * 100:.2f}% ( {unique_aligned_tgt_count} / {total_tgt_funcs} ) - 去重后的参与对齐 Target 函数量 / Target 核心模块下的函数总量",
                "functional_overlap_ratio_iou": f"{functional_overlap_ratio * 100:.2f}% ( {total_aligned_funcs} / {union_funcs} ) - 对齐的函数量 / (Source函数总量 + Target函数总量 - 对齐函数量)",
                "unique_functional_overlap_ratio_iou": f"{unique_functional_overlap_ratio * 100:.2f}% ( {min(unique_aligned_src_count, unique_aligned_tgt_count)} / {unique_union_funcs} ) - 基于去重函数参与量估算的功能重合度",
                "architecture_fragmentation_index": f"{fragmentation_index:.1f} - Target 对齐模块数 / Source 对齐模块数",
                "mapping_compression_ratio": f"{mapping_compression_ratio:.2f}x ( {unique_aligned_src_count} / {unique_aligned_tgt_count} unique functions ) - 去重 Source 对齐函数数 / 去重 Target 参与函数数，>1 表示 Target 用更少函数承接更多 Source 语义",
                "target_reuse_factor": f"{target_reuse_factor:.2f}x ( {total_aligned_funcs} / {unique_aligned_tgt_count} ) - 对齐 pair 数 / 去重 Target 参与函数数，反映 Target 函数被多个 Source 函数复用的程度",
                "api_bloat_ratio": f"{api_bloat_ratio:.2f}x ( {total_tgt_funcs} / {total_src_funcs} functions ) - Target 对齐模块总函数量 / Source 对齐模块总函数量",
                "code_volume_loc_bloat_ratio": f"{loc_bloat_ratio:.2f}x ( {total_tgt_loc} / {total_src_loc} lines ) - Target 核心模块总代码行数(LOC) / Source 核心模块总代码行数(LOC)",
                "source_orphan_rate": f"{source_orphan_rate * 100:.2f}% ( {source_orphan_count} / {total_src_funcs} ) - Source 中未被翻译的函数量 / Source 总函数量",
                "target_native_rate": f"{target_native_rate * 100:.2f}% ( {target_native_count} / {total_tgt_funcs} ) - Target 中无对应C源码的独创函数量 / Target 总函数量",
                "target_unsafe_dependency_rate": f"{unsafe_rate * 100:.2f}% ( {total_unsafe_funcs} / {total_tgt_funcs} ) - Target 中带有 unsafe 标记或代码块的函数量 / Target 总函数量",
                "micro_alignment_confidence_rate": f"{confidence_rate * 100:.2f}% ( {high_confidence_funcs} / {total_aligned_funcs} ) - 大模型标记为High确信度的对齐数量 / 总共对齐的函数对数量"
            }
        }
        
        alignment_report["macro_alignment_score"] = round(macro_score, 2)
        alignment_report["quantitative_metrics"] = metrics
        
        return alignment_report
