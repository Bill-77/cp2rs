import json
import re
from rpg_builder.llm_client import LLMClient
from .prompts import PROMPT_MACRO_ALIGNMENT, PROMPT_MICRO_ALIGNMENT

class FunnelAligner:
    """
    CP2RS Phase 3A: 模块对齐引擎
    双重漏斗设计：先根据RPG的根和中间节点宏观对齐架构模块（Root），
    再根据schema中对齐模块下函数的 body 微观对齐源码函数。
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def _extract_json_from_reply(self, reply: str) -> list:
        """防御性 JSON 解析：优先提取 <output> 标签，Fallback 到 Markdown 标记"""
        reply = reply.strip()
        json_str = ""

        # 1. 防御1：提取 <output> 标签内的内容
        output_pattern = re.search(r'<output>\s*(.*?)\s*</output>', reply, re.DOTALL)
        if output_pattern:
            json_str = output_pattern.group(1)
        else:
            # 2. 防御2 (Fallback)：如果大模型忘记写标签，尝试找 Markdown
            regex_pattern = r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```'
            json_pattern = re.search(regex_pattern, reply, re.DOTALL)
            if json_pattern:
                json_str = json_pattern.group(1)
            else:
                # 3. 防御3：直接找最外层的方括号或大括号
                start = reply.find('[')
                end = reply.rfind(']')
                if start != -1 and end != -1:
                    json_str = reply[start:end+1]
                else:
                    json_str = reply

        # 尝试反序列化
        try:
            # 额外清理：有时候大模型在 <output> 里还多加了 ```json 
            json_str = json_str.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:]
            if json_str.startswith('```'):
                json_str = json_str[3:]
            if json_str.endswith('```'):
                json_str = json_str[:-3]
                
            return json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            print(f"⚠️ LLM 返回 JSON 解析失败: {e}\n原始返回内容:\n{reply}")
            return []
            
    # ==========================================
    # 🎯 重构点 1：融入架构拓扑边 (Edges)
    # ==========================================
    def _macro_align_modules(self, src_rpg, tgt_rpg) -> list:
        def _build_architecture_summary(rpg):
            summaries = ["[模块定义 (Root Nodes)]"]
            # 1. 提取 Root 及其包含的文件 (Intermediate)
            for root in rpg["nodes"].get("root_nodes", []):
                # 假设 root 包含了它拥有的 intermediate 节点 ID 列表
                contained_files = root.get("intermediate_ids", [])
                summaries.append(f"模块 ID: {root['id']}")
                summaries.append(f"  - 语义名称: {root.get('semantic_name', '')}")
                summaries.append(f"  - 详细描述: {root.get('description', '')}")
                summaries.append(f"  - 包含文件数: {len(contained_files)} 个")
            
            # 2. 提取拓扑边 (Edges) - 这对架构理解至关重要！
            summaries.append("\n[模块间数据流与调用拓扑 (Edges)]")
            
            # 正确解析 RPG 的 edges 字典结构
            edges_dict = rpg.get("edges", {})
            inter_edges = edges_dict.get("inter_module_edges", [])
            
            for edge in inter_edges:
                source = edge.get("source", "Unknown")
                target = edge.get("target", "Unknown")
                desc = edge.get("description", "依赖")
                summaries.append(f"  - {source} ---> {target} (关系: {desc})")
            
            return "\n".join(summaries)

        prompt_content = PROMPT_MACRO_ALIGNMENT.format(
            src_summaries=_build_architecture_summary(src_rpg),
            tgt_summaries=_build_architecture_summary(tgt_rpg)
        )
        
        messages = [{"role": "user", "content": prompt_content}]
        reply = self.llm.chat_completion(messages, temperature=0.1)
        return self._extract_json_from_reply(reply)

    # ==========================================
    # 🎯 重构点 2：极其优雅的文件级溯源 (彻底抛弃 Leaf Nodes)
    # ==========================================
    def _fetch_functions_by_root(self, root_ids_str, rpg, parsed_db) -> list:
        """
        顺藤摸瓜：解析 Root ID (支持逗号分隔的1对N) -> 通过 parent_root 找到文件名 -> 去 DB 提取所有函数。
        """
        results = []
        if not root_ids_str: 
            return results
            
        # 1. 解析可能由逗号分隔的 root_ids (完美支持 1-to-N 和 N-to-M 映射)
        root_ids = [r.strip() for r in root_ids_str.split(',')]
        
        file_paths = []
        
        # 2. 遍历中间节点，通过 parent_root 字段逆向查找它属于哪个 Root
        for inter in rpg["nodes"].get("intermediate_nodes", []):
            if inter.get("parent_root") in root_ids:
                file_paths.append(inter.get("file_path"))
                
        # 3. 去重文件名，拿着它们直接去 Phase 1 Database 里“进货”
        for f_path in set(file_paths):
            file_data = parsed_db.get("files", {}).get(f_path)
            if not file_data: 
                continue
            
            # 提取扁平函数 (C 语言或独立函数)
            for func in file_data.get("functions", []) + file_data.get("standalone_functions", []):
                if func.get("body"):
                    # 动态生成绝对唯一的 UUID，包含文件名以防重名
                    func_uuid = f"{f_path}::{func.get('name')}"
                    results.append({"uuid": func_uuid, "signature": func.get("signature", ""), "body": func.get("body")})
                    
            # 提取类成员函数 (C++)
            for cls in file_data.get("classes", []):
                for method in cls.get("methods", []):
                    if method.get("body"):
                        func_uuid = f"{f_path}::{cls.get('name')}::{method.get('name')}"
                        results.append({"uuid": func_uuid, "signature": method.get("signature", ""), "body": method.get("body")})
            
            # 提取 Impl 成员函数 (Rust)
            for impl in file_data.get("impl_blocks", []):
                for method in impl.get("methods", []):
                    if method.get("body"):
                        func_uuid = f"{f_path}::{impl.get('target_type')}::{method.get('name')}"
                        results.append({"uuid": func_uuid, "signature": method.get("signature", ""), "body": method.get("body")})
                        
        return results

    def _micro_align_functions(self, src_funcs, tgt_funcs) -> list:
        # [此方法保持不变，直接投喂组装好的代码块给 LLM]
        if not src_funcs or not tgt_funcs: return []

        def _build_code_blocks(funcs):
            blocks = []
            for f in funcs:
                blocks.append(f"====== [UUID: {f['uuid']}] ======\n{f['body']}\n")
            return "\n".join(blocks)

        prompt_content = PROMPT_MICRO_ALIGNMENT.format(
            src_code_blocks=_build_code_blocks(src_funcs),
            tgt_code_blocks=_build_code_blocks(tgt_funcs)
        )
        
        messages = [{"role": "user", "content": prompt_content}]
        reply = self.llm.chat_completion(messages, temperature=0.1)
        return self._extract_json_from_reply(reply)

    def run_alignment(self, src_rpg_path, tgt_rpg_path, src_db_path, tgt_db_path):
        print("🔍 [Phase 3A] 启动双重漏斗对齐引擎...")
        
        with open(src_rpg_path, 'r', encoding='utf-8') as f: src_rpg = json.load(f)
        with open(tgt_rpg_path, 'r', encoding='utf-8') as f: tgt_rpg = json.load(f)
        with open(src_db_path, 'r', encoding='utf-8') as f: src_db = json.load(f)
        with open(tgt_db_path, 'r', encoding='utf-8') as f: tgt_db = json.load(f)

        print("   -> 正在进行宏观架构对齐 (Root & Edges 拓扑)...")
        macro_mapping = self._macro_align_modules(src_rpg, tgt_rpg)
        
        final_alignment_report = {"macro_alignment_score": 0, "aligned_modules": []}
        print(f"   -> 宏观对齐完成，找到 {len(macro_mapping)} 对相似模块。开始源码级微观对齐...")
        
        for module_pair in macro_mapping:
            src_root_id = module_pair.get("src_root_id")
            tgt_root_id = module_pair.get("tgt_root_id")
            if not src_root_id or not tgt_root_id: continue
            
            # 【核心改变】：彻底抛弃 Leaf Nodes 遍历，直接调用文件级溯源！
            src_funcs_with_body = self._fetch_functions_by_root(src_root_id, src_rpg, src_db)
            tgt_funcs_with_body = self._fetch_functions_by_root(tgt_root_id, tgt_rpg, tgt_db)
            
            print(f"      - 正在对齐 [ {src_root_id} 🆚 {tgt_root_id} ] (提取到 {len(src_funcs_with_body)} vs {len(tgt_funcs_with_body)} 个源码体)")
            
            func_mapping = self._micro_align_functions(src_funcs_with_body, tgt_funcs_with_body)
            
            final_alignment_report["aligned_modules"].append({
                "src_module": src_root_id,
                "tgt_module": tgt_root_id,
                "justification": module_pair.get("justification", ""),
                "aligned_functions": func_mapping 
            })

        return final_alignment_report