import json

class StaticAnalyzer:
    """
    CP2RS Phase 3C: 全仓库静态特征扫描器 (精确去重增强版)
    """
    def __init__(self):
        pass

    def _extract_unique_functions(self, file_path: str, file_data: dict) -> list:
        """确保在全仓扫描时不发生重复计数"""
        unique_funcs = {}
        for f in file_data.get("functions", []) + file_data.get("standalone_functions", []):
            if f.get("body"):
                uid = f"{file_path}::{f.get('name')}"
                unique_funcs[uid] = f
                
        for cls in file_data.get("classes", []):
            for m in cls.get("methods", []):
                if m.get("body"):
                    uid = f"{file_path}::{cls.get('name')}::{m.get('name')}"
                    unique_funcs[uid] = m
                    
        for impl in file_data.get("impl_blocks", []):
            for m in impl.get("methods", []):
                if m.get("body"):
                    uid = f"{file_path}::{impl.get('target_type')}::{m.get('name')}"
                    unique_funcs[uid] = m
                    
        return list(unique_funcs.values())

    def _scan_database(self, db_data: dict, is_target: bool = False) -> dict:
        stats = {
            "total_files": 0,
            "total_functions": 0,
            "total_loc": 0,
            "unsafe_functions": 0
        }

        files = db_data.get("files", {})
        stats["total_files"] = len(files)

        for file_path, file_data in files.items():
            # 使用统一标准的去重器
            clean_funcs = self._extract_unique_functions(file_path, file_data)

            for func in clean_funcs:
                body = func.get("body", "")
                stats["total_functions"] += 1
                stats["total_loc"] += len(body.splitlines())

                if is_target:
                    signature = func.get("signature", "")
                    if "unsafe " in signature or "unsafe {" in body or "unsafe{" in body:
                        stats["unsafe_functions"] += 1

        return stats

    def run_global_analysis(self, src_db_path: str, tgt_db_path: str) -> dict:
        print("\n" + "="*50)
        print("🔎 [Phase 3C] 启动全仓库静态特征扫描 (Global Static Analysis)...")
        
        with open(src_db_path, 'r', encoding='utf-8') as f: src_db = json.load(f)
        with open(tgt_db_path, 'r', encoding='utf-8') as f: tgt_db = json.load(f)

        src_stats = self._scan_database(src_db, is_target=False)
        tgt_stats = self._scan_database(tgt_db, is_target=True)

        print(f"   -> 全仓扫描完毕: Source ({src_stats['total_functions']} 独立函数), Target ({tgt_stats['total_functions']} 独立函数)")

        global_loc_bloat = tgt_stats["total_loc"] / src_stats["total_loc"] if src_stats["total_loc"] > 0 else 0
        global_api_bloat = tgt_stats["total_functions"] / src_stats["total_functions"] if src_stats["total_functions"] > 0 else 0
        global_unsafe_rate = tgt_stats["unsafe_functions"] / tgt_stats["total_functions"] if tgt_stats["total_functions"] > 0 else 0

        report = {
            "evaluation_type": "Phase 3C - Global Static Analysis",
            "repository_stats": {
                "source_repository": src_stats,
                "target_repository": tgt_stats
            },
            "global_metrics": {
                "global_code_volume_loc_bloat": {
                    "value": f"{global_loc_bloat:.2f}x",
                    "raw_fraction": f"{tgt_stats['total_loc']} / {src_stats['total_loc']}",
                    "formula": "Target 全仓总代码行数 / Source 全仓总代码行数"
                },
                "global_api_bloat_ratio": {
                    "value": f"{global_api_bloat:.2f}x",
                    "raw_fraction": f"{tgt_stats['total_functions']} / {src_stats['total_functions']}",
                    "formula": "Target 全仓总函数量 / Source 全仓总函数量"
                },
                "global_unsafe_dependency_rate": {
                    "value": f"{global_unsafe_rate * 100:.2f}%",
                    "raw_fraction": f"{tgt_stats['unsafe_functions']} / {tgt_stats['total_functions']}",
                    "formula": "Target 全仓 unsafe 函数量 / Target 全仓总函数量"
                }
            }
        }
        return report