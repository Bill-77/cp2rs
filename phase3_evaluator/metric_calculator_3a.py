import json

class MetricCalculator3A:
    """
    CP2RS Phase 3A: 量化打分引擎
    纯代码计算硬核指标，剥离大模型的主观性，支持完全复现。
    以宏观模块覆盖率和微观函数覆盖率为核心驱动指标，包含架构碎片化指数、微观对齐置信度、接口膨胀率、孤儿函数率、交并比(IoU)、代码行数(LOC)膨胀率以及 Unsafe 质量探针。
    """
    def __init__(self):
        pass

    def _extract_unique_functions(self, file_path: str, file_data: dict) -> list:
        """核心修复：通过动态构建 UUID，彻底消除 functions 与 standalone_functions 的重复计数"""
        unique_funcs = {}
        
        # 1. 扁平函数去重
        for f in file_data.get("functions", []) + file_data.get("standalone_functions", []):
            if f.get("body"):
                uid = f"{file_path}::{f.get('name')}"
                unique_funcs[uid] = f
                
        # 2. 类方法去重 (C++)
        for cls in file_data.get("classes", []):
            for m in cls.get("methods", []):
                if m.get("body"):
                    uid = f"{file_path}::{cls.get('name')}::{m.get('name')}"
                    unique_funcs[uid] = m
                    
        # 3. Impl 方法去重 (Rust)
        for impl in file_data.get("impl_blocks", []):
            for m in impl.get("methods", []):
                if m.get("body"):
                    uid = f"{file_path}::{impl.get('target_type')}::{m.get('name')}"
                    unique_funcs[uid] = m
                    
        return list(unique_funcs.values())

    def _extract_module_statistics(self, root_ids_str, rpg, parsed_db, is_target=False) -> dict:
        """
        全能特征提取器：返回函数总量、代码总行数(LOC)、Unsafe函数数量
        """
        stats = {"total_funcs": 0, "total_loc": 0, "unsafe_funcs": 0}
        if not root_ids_str: 
            return stats
            
        root_ids = [r.strip() for r in root_ids_str.split(',')]
        file_paths = []
        
        # 顺藤摸瓜找文件
        for inter in rpg["nodes"].get("intermediate_nodes", []):
            if inter.get("parent_root") in root_ids:
                file_paths.append(inter.get("file_path"))
                
        # 遍历文件提取特征
        for f_path in set(file_paths):
            file_data = parsed_db.get("files", {}).get(f_path)
            if not file_data: continue
            
            # # 聚合当前文件的所有函数体
            # all_funcs = file_data.get("functions", []) + file_data.get("standalone_functions", [])
            # for cls in file_data.get("classes", []):
            #     all_funcs.extend(cls.get("methods", []))
            # for impl in file_data.get("impl_blocks", []):
            #     all_funcs.extend(impl.get("methods", []))
                
            # # 统计核心指标
            # for func in all_funcs:
            #     body = func.get("body")
            #     if body:
            #         stats["total_funcs"] += 1
            #         # 粗略统计代码行数 (LOC)
            #         stats["total_loc"] += len(body.splitlines())
                    
            #         # 质量探针：扫描 Target 中的 unsafe 行为
            #         if is_target:
            #             signature = func.get("signature", "")
            #             # 检查函数签名是否为 unsafe fn，或者函数体内部是否包含 unsafe 块
            #             if "unsafe " in signature or "unsafe {" in body or "unsafe{" in body:
            #                 stats["unsafe_funcs"] += 1

            # 使用全新的去重方法获取干净的函数列表
            clean_funcs = self._extract_unique_functions(f_path, file_data)
            
            for func in clean_funcs:
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
                
            total_aligned_funcs += len(funcs)
            high_confidence_funcs += sum(1 for f in funcs if f.get("confidence", "").upper() == "HIGH")
            
            src_stats = self._extract_module_statistics(mod["src_module"], src_rpg, src_db, is_target=False)
            tgt_stats = self._extract_module_statistics(mod["tgt_module"], tgt_rpg, tgt_db, is_target=True)
            
            total_src_funcs += src_stats["total_funcs"]
            total_src_loc += src_stats["total_loc"]
            total_tgt_funcs += tgt_stats["total_funcs"]
            total_tgt_loc += tgt_stats["total_loc"]
            total_unsafe_funcs += tgt_stats["unsafe_funcs"]

            # 按要求的顺序重建字典
            ordered_mod = {
                "src_module": mod["src_module"],
                "src_module_description": src_desc,
                "tgt_module": mod["tgt_module"],
                "tgt_module_description": tgt_desc,
                "justification": mod.get("justification", ""),
                "aligned_functions": funcs
            }
            ordered_aligned_modules.append(ordered_mod)

        # 替换为排好序的新数组
        alignment_report["aligned_modules"] = ordered_aligned_modules
        
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
        macro_coverage = len(aligned_src_roots) / src_total_roots if src_total_roots > 0 else 0
        micro_coverage = total_aligned_funcs / total_src_funcs if total_src_funcs > 0 else 0
        macro_score = (macro_coverage * 70) + (micro_coverage * 30)

        # 🥈 深度透视参考指标
        # 1. 架构碎片化指数
        fragmentation_index = len(aligned_tgt_roots) / len(aligned_src_roots) if len(aligned_src_roots) > 0 else 0
        
        # 2. 功能重合度 (Jaccard Index / IoU) 
        union_funcs = (total_src_funcs + total_tgt_funcs) - total_aligned_funcs
        functional_overlap_ratio = total_aligned_funcs / union_funcs if union_funcs > 0 else 0
        
        # 3. 体积膨胀率 (API 个数 vs LOC 行数)
        api_bloat_ratio = total_tgt_funcs / total_src_funcs if total_src_funcs > 0 else 0
        loc_bloat_ratio = total_tgt_loc / total_src_loc if total_src_loc > 0 else 0
        
        # 4. 孤儿与原生率
        source_orphan_count = total_src_funcs - total_aligned_funcs
        target_native_count = total_tgt_funcs - total_aligned_funcs
        source_orphan_rate = source_orphan_count / total_src_funcs if total_src_funcs > 0 else 0
        target_native_rate = target_native_count / total_tgt_funcs if total_tgt_funcs > 0 else 0
        
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
                "union_functions": f"{union_funcs} - 两个仓库对齐模块下函数的去重并集总数",
                "total_source_loc": f"{total_src_loc} - Source 对齐模块的总代码行数 (Lines of Code)",
                "total_target_loc": f"{total_tgt_loc} - Target 对齐模块的总代码行数 (Lines of Code)",
                "source_orphan_functions": f"{source_orphan_count} - Source 中被时代淘汰或未被翻译的孤儿函数量",
                "target_native_functions": f"{target_native_count} - Target 中独创的、无 C 源码对应的原生函数量",
                "target_unsafe_functions": f"{total_unsafe_funcs} - Target 核心模块中带有 unsafe 标记或代码块的函数量",
                "high_confidence_alignments": f"{high_confidence_funcs} - 被大模型评估为 High 确信度的微观对齐函数量"
            },
            "derived_ratio_metrics": {
                "source_macro_coverage_rate": f"{macro_coverage * 100:.2f}% ( {len(aligned_src_roots)} / {src_total_roots} ) - 对齐的 Source 核心模块数 / Source 仓库总模块数",
                "source_micro_coverage_rate": f"{micro_coverage * 100:.2f}% ( {total_aligned_funcs} / {total_src_funcs} ) - 成功对齐的函数对数量 / Source 核心模块下的函数总量",
                "functional_overlap_ratio_iou": f"{functional_overlap_ratio * 100:.2f}% ( {total_aligned_funcs} / {union_funcs} ) - 对齐的函数量 / (Source函数总量 + Target函数总量 - 对齐函数量)",
                "architecture_fragmentation_index": f"{fragmentation_index:.1f} - Target 对齐模块数 / Source 对齐模块数",
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