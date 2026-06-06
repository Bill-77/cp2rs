import json
import re
import time
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

    def _extract_json_from_reply(self, reply: str):
        """防御性 JSON 解析：正则暴洗不合法转义，彻底阻断空弹欺骗"""
        reply = reply.strip()
        json_str = ""

        # 1. 防御1：提取 <output> 标签内的内容
        output_pattern = re.search(r'<output>\s*(.*?)\s*</output>', reply, re.DOTALL)
        if output_pattern:
            json_str = output_pattern.group(1)
        else:
            # 2. 防御2 (Fallback)：使用 \x60 规避 UI 渲染截断
            regex_pattern = r'\x60\x60\x60(?:json)?\s*(\[.*?\]|\{.*?\})\s*\x60\x60\x60'
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

        json_str = json_str.strip()
        # 使用 \x60 进行字符串切片清理，\x60 是反引号的 ASCII 码，常用于 Markdown 代码块，能有效规避大模型输出中的 UI 截断问题
        if json_str.startswith('\x60\x60\x60json'): json_str = json_str[7:]
        if json_str.startswith('\x60\x60\x60'): json_str = json_str[3:]
        if json_str.endswith('\x60\x60\x60'): json_str = json_str[:-3]
        json_str = json_str.strip()

        # 🛡️ 核心修复 1：暴力清洗不合法的 JSON 转义字符
        # 修复大模型乱写的 \uXXXX (如果 \u 后面不是 4 位合法十六进制，就把它转义为 \\u)：只匹配前面没有反斜杠的 \u
        json_str = re.sub(r'(?<!\\)\\u(?![0-9a-fA-F]{4})', r'\\\\u', json_str)
        # 修复独立的非法反斜杠 (不在 JSON 官方合法转义集 \" \\ \/ \b \f \n \r \t 里的且只匹配前面没有反斜杠的 \)
        json_str = re.sub(r'(?<!\\)\\([^"\\/bfnrtu])', r'\\\\\\1', json_str)

        try:
            # 开启 strict=False 允许部分控制字符的宽容解析
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError as e:
            print(f"         ⚠️ JSON 解析失败 (已被拦截，将触发重试): {e}")

            # ==========================================
            # 提取报错位置前后 40 个字符，看看大模型到底写了什么导致json的提取失败
            err_pos = e.pos
            start_pos = max(0, err_pos - 40)
            end_pos = min(len(json_str), err_pos + 40)
            crime_scene = json_str[start_pos:end_pos]
            print(f"         🚨 [案发现场截取] -> ...{crime_scene}...")
            
            # 为了方便完整查看，把这批次的脏数据完整写到本地文件
            with open("debug_crime_scene.json", "w", encoding="utf-8") as df:
                df.write(json_str)
            print("         📝 [完整脏数据] 已保存至当前目录的 debug_crime_scene.json 文件中。")
            # ==========================================
            
            # 核心修复 2：失败必须返回 None，绝不能返回 []
            # 这样外层的 while/for 循环才能判定 batch_success = False 并触发重新请求
            return None
            
    # ==========================================
    # 🎯 重构点 1：融入架构拓扑边 (Edges)
    # ==========================================
    def _macro_align_modules(self, src_rpg, tgt_rpg) -> list:
        def _build_architecture_summary(rpg):
            nodes = rpg.get("nodes", {})
            root_nodes = nodes.get("root_nodes", [])
            intermediate_nodes = nodes.get("intermediate_nodes", [])

            root_to_intermediates = {root.get("id"): [] for root in root_nodes if root.get("id")}
            orphan_intermediates = []
            for inter in intermediate_nodes:
                parent_root = inter.get("parent_root")
                if parent_root in root_to_intermediates:
                    root_to_intermediates[parent_root].append(inter)
                else:
                    orphan_intermediates.append(inter)

            summaries = ["[模块定义 (Root Nodes + 下属文件)]"]
            # 1. 提取 Root 及其包含的文件 (Intermediate)
            for root in root_nodes:
                root_id = root.get("id", "UnknownRoot")
                contained_files = sorted(
                    root_to_intermediates.get(root_id, []),
                    key=lambda item: item.get("file_path", "")
                )
                summaries.append(f"模块 ID: {root_id}")
                summaries.append(f"  - 语义名称: {root.get('semantic_name', '')}")
                summaries.append(f"  - 详细描述: {root.get('description', '')}")
                summaries.append(f"  - 包含文件数: {len(contained_files)} 个")
                for inter in contained_files:
                    inter_id = inter.get("id", "UnknownIntermediate")
                    file_path = inter.get("file_path", "")
                    semantic_name = inter.get("semantic_name", "")
                    description = inter.get("description", "")
                    summaries.append(f"    * {inter_id} | {file_path} | {semantic_name}: {description}")

            if orphan_intermediates:
                summaries.append("\n[未挂载到已知 Root 的 Intermediate 节点]")
                for inter in orphan_intermediates:
                    summaries.append(
                        f"  - {inter.get('id', 'UnknownIntermediate')} | "
                        f"parent_root={inter.get('parent_root', '')} | "
                        f"{inter.get('file_path', '')}"
                    )
            
            # 2. 提取拓扑边 (Edges) - 这对架构理解至关重要！
            summaries.append("\n[模块间数据流与调用拓扑 (Inter-Root Edges)]")
            
            # 正确解析 RPG 的 edges 字典结构
            edges_dict = rpg.get("edges", {})
            inter_edges = edges_dict.get("inter_module_edges", [])
            
            if not inter_edges:
                summaries.append("  - 无显式模块间边")
            for edge in inter_edges:
                source = edge.get("source", "Unknown")
                target = edge.get("target", "Unknown")
                desc = edge.get("description", "依赖")
                evidence = edge.get("evidence", "")
                summaries.append(f"  - {source} ---> {target} (关系: {desc}; 证据: {evidence})")

            summaries.append("\n[模块内文件执行拓扑 (Intra-Root Intermediate Edges)]")
            intra_edges = edges_dict.get("intra_module_edges", [])
            if not intra_edges:
                summaries.append("  - 无显式模块内边")
            for edge in intra_edges:
                source = edge.get("source", "Unknown")
                target = edge.get("target", "Unknown")
                relation_type = edge.get("relation_type", "dependency")
                desc = edge.get("description", "依赖")
                evidence = edge.get("evidence", "")
                summaries.append(f"  - {source} ---> {target} ({relation_type}: {desc}; 证据: {evidence})")
            
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
        提取函数体：解析 Root ID (支持逗号分隔的1对N) -> 通过 parent_root 找到文件名 -> 去 DB 提取所有函数。
        """
        if not root_ids_str: 
            return []
            
        # 1. 解析可能由逗号分隔的 root_ids (完美支持 1-to-N 和 N-to-M 映射)
        root_ids = [r.strip() for r in root_ids_str.split(',')]
        file_paths = []
        
        # 2. 遍历中间节点，通过 parent_root 字段逆向查找它属于哪个 Root
        for inter in rpg["nodes"].get("intermediate_nodes", []):
            if inter.get("parent_root") in root_ids:
                file_paths.append(inter.get("file_path"))
                
        # 3. 去重文件名，拿着它们去 Phase 1 Database 里提取函数体，并去重函数
        unique_funcs = {}
        for f_path in set(file_paths):
            file_data = parsed_db.get("files", {}).get(f_path)
            if not file_data: 
                continue
            
            # 提取扁平函数 (C 语言或独立函数)
            for func in file_data.get("functions", []) + file_data.get("standalone_functions", []):
                if func.get("body"):
                    uid = f"{f_path}::{func.get('name')}"
                    unique_funcs[uid] = {"uuid": uid, "signature": func.get("signature", ""), "body": func.get("body")}
                    
            # 提取类成员函数 (C++)
            for cls in file_data.get("classes", []):
                for method in cls.get("methods", []):
                    if method.get("body"):
                        uid = f"{f_path}::{cls.get('name')}::{method.get('name')}"
                        unique_funcs[uid] = {"uuid": uid, "signature": method.get("signature", ""), "body": method.get("body")}
            
            # 提取 Impl 成员函数 (Rust)
            for impl in file_data.get("impl_blocks", []):
                for method in impl.get("methods", []):
                    if method.get("body"):
                        uid = f"{f_path}::{impl.get('target_type')}::{method.get('name')}"
                        unique_funcs[uid] = {"uuid": uid, "signature": method.get("signature", ""), "body": method.get("body")}
                        
        # 返回去重后的纯净函数列表
        return list(unique_funcs.values())

    def _micro_align_functions(self, src_funcs, tgt_funcs, batch_size=20) -> list:
        """
        第二重漏斗：微观对齐。
        强制启用分批(Batching)与阻断式重试，避免 Token 爆炸和静默失败。
        """
        if not src_funcs or not tgt_funcs:
            return []

        def _build_code_blocks(funcs):
            blocks = []
            for f in funcs:
                blocks.append(f"====== [UUID: {f['uuid']}] ======\n{f['body']}\n")
            return "\n".join(blocks)

        # 目标端作为全量知识库，不进行切分
        tgt_code_str = _build_code_blocks(tgt_funcs)
        
        all_aligned_mappings = []
        total_batches = (len(src_funcs) + batch_size - 1) // batch_size

        # 将 Source 源码进行分批
        for i in range(0, len(src_funcs), batch_size):
            batch_num = (i // batch_size) + 1
            src_batch = src_funcs[i:i+batch_size]
            src_code_str = _build_code_blocks(src_batch)
            
            prompt_content = PROMPT_MICRO_ALIGNMENT.format(
                src_code_blocks=src_code_str,
                tgt_code_blocks=tgt_code_str
            )
            
            messages = [{"role": "user", "content": prompt_content}]
            
            max_retries = 3
            batch_success = False
            
            for attempt in range(max_retries):
                print(f"      - [微观对齐] 正在处理第 {batch_num}/{total_batches} 批次 ({len(src_batch)} 个 Source 函数) - 尝试 {attempt + 1}/{max_retries}...")
                
                try:
                    reply = self.llm.chat_completion(messages, temperature=0.1)
                    
                    if not reply or not reply.strip():
                        print("         ⚠️ 警告：大模型返回空字符串，准备重试...")
                        time.sleep(2)
                        continue
                        
                    parsed_json = self._extract_json_from_reply(reply)
                    
                    # 只有当解析成功并返回了 list 时才算通过 (避开 None)
                    if isinstance(parsed_json, list):
                        all_aligned_mappings.extend(parsed_json)
                        batch_success = True
                        break
                    else:
                        print("         ⚠️ 警告：JSON 提取结果不合法，准备重试...")
                        time.sleep(2)
                        
                except Exception as e:
                    print(f"         ❌ 调用或网络异常: {e}")
                    time.sleep(3)
            
            if not batch_success:
                print(f"      🚨 放弃批次 {batch_num}：已达到最大重试次数，部分对齐数据可能丢失。")

        return all_aligned_mappings

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
