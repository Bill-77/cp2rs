import re
import json
from pathlib import PurePosixPath
from .ir_utils import create_ir_skeleton, fetch_requested_bodies

def extract_xml_tag(text, tag_name):
    """工具函数：利用正则表达式提取 XML 标签内的内容"""
    pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None

# 对付脏字符和格式错位的工具函数
def clean_and_parse_json(json_str):
    """清洗不间断空格等非法字符，并尝试暴力提取 JSON {} 或 []"""
    if not json_str:
        raise ValueError("传入的 JSON 字符串为空")
        
    # 1. 净化特殊空格 (\xa0 等)
    clean_text = json_str.replace('\xa0', ' ').replace('\u200b', '').strip()
    
    # 2. 尝试直接解析
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        # 3. 终极回退机制：暴力寻找最外层的 {} (字典) 或 [] (列表)
        start_dict, end_dict = clean_text.find('{'), clean_text.rfind('}')
        start_list, end_list = clean_text.find('['), clean_text.rfind(']')
        
        # 判断是字典结构还是列表结构在最外层
        if start_dict != -1 and end_dict != -1 and (start_list == -1 or start_dict < start_list):
            target_str = clean_text[start_dict : end_dict + 1]
        elif start_list != -1 and end_list != -1:
            target_str = clean_text[start_list : end_list + 1]
        else:
            raise ValueError("无法在字符串中找到有效的 {} 或 [] 结构。")
            
        return json.loads(target_str)


def _normalize_file_path(path):
    """Normalize model-produced file paths to the Phase 1 DB path style."""
    if not path:
        return ""
    normalized = str(path).replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def validate_and_repair_rpg_file_paths(rpg_data, full_ir, prefix=""):
    """
    Ensure every Intermediate.file_path points to an existing Phase 1 file.
    LLMs sometimes hallucinate near-miss paths such as src/lib/foo.cpp instead
    of src/lib_json/foo.cpp; repair only when there is a unique deterministic
    match. Ambiguous or unknown paths fail fast so Phase 3A never receives an
    unusable RPG.
    """
    valid_paths = {_normalize_file_path(path) for path in full_ir.get("files", {})}
    if not valid_paths:
        raise ValueError("Phase 1 IR has no files; cannot validate RPG file_path entries.")

    basename_index = {}
    for path in valid_paths:
        basename_index.setdefault(PurePosixPath(path).name, []).append(path)

    nodes = rpg_data.get("nodes", {}) if isinstance(rpg_data, dict) else {}
    intermediate_nodes = nodes.get("intermediate_nodes", [])
    repairs = []
    unresolved = []

    for node in intermediate_nodes:
        original_path = node.get("file_path", "")
        normalized_path = _normalize_file_path(original_path)

        if normalized_path in valid_paths:
            node["file_path"] = normalized_path
            continue

        basename = PurePosixPath(normalized_path).name
        basename_matches = basename_index.get(basename, [])
        if len(basename_matches) == 1:
            repaired_path = basename_matches[0]
            node["file_path"] = repaired_path
            repairs.append((original_path, repaired_path))
            continue

        unresolved.append({
            "id": node.get("id", ""),
            "file_path": original_path,
            "candidate_count": len(basename_matches),
            "candidates": sorted(basename_matches)[:10],
        })

    if repairs:
        print(f"{prefix}   🛠️ [RPG路径修复] 已修复 {len(repairs)} 个 Intermediate.file_path。")
        for before, after in repairs:
            print(f"{prefix}      - {before} -> {after}")

    if unresolved:
        raise ValueError(
            "RPG contains Intermediate.file_path entries that do not exist in Phase 1 DB "
            f"and cannot be repaired uniquely: {json.dumps(unresolved, ensure_ascii=False)}"
        )

    return rpg_data


def _path_stem_tokens(path):
    stem = PurePosixPath(path).stem.lower()
    return [token for token in re.split(r"[^a-z0-9]+", stem) if token]


def _is_probable_pair(missing_path, existing_path):
    missing_stem = PurePosixPath(missing_path).stem.lower()
    existing_stem = PurePosixPath(existing_path).stem.lower()
    if missing_stem == existing_stem:
        return True
    if missing_stem.endswith("_" + existing_stem) or existing_stem.endswith("_" + missing_stem):
        return True
    missing_tokens = set(_path_stem_tokens(missing_path))
    existing_tokens = set(_path_stem_tokens(existing_path))
    if len(missing_tokens) >= 2 and len(existing_tokens) >= 2:
        shorter = missing_tokens if len(missing_tokens) <= len(existing_tokens) else existing_tokens
        return shorter.issubset(missing_tokens & existing_tokens)
    return False


def _file_has_executable_definitions(file_data):
    def has_body(item):
        if "has_body" in item:
            return item.get("has_body") is True
        return bool(item.get("body"))

    for func in file_data.get("functions", []) + file_data.get("standalone_functions", []):
        if has_body(func):
            return True
    for cls in file_data.get("classes", []):
        for method in cls.get("methods", []):
            if has_body(method):
                return True
    for impl in file_data.get("impl_blocks", []):
        for method in impl.get("methods", []):
            if has_body(method):
                return True
    return False


def mount_missing_phase1_files(rpg_data, full_ir, prefix=""):
    """
    Ensure Phase 2 does not silently drop parsed implementation files.

    The LLM may correctly describe a header/source subsystem but forget to emit
    one physical Intermediate node. When there is a unique deterministic
    header/source sibling in the existing RPG, attach the missing file to that
    sibling's root. Otherwise fail fast; a partial RPG would break Phase 3A.
    """
    valid_paths = {_normalize_file_path(path) for path in full_ir.get("files", {})}
    nodes = rpg_data.setdefault("nodes", {})
    intermediate_nodes = nodes.setdefault("intermediate_nodes", [])
    mounted_paths = {
        _normalize_file_path(node.get("file_path"))
        for node in intermediate_nodes
        if node.get("file_path")
    }
    missing_paths = sorted(valid_paths - mounted_paths)
    if not missing_paths:
        return rpg_data

    root_nodes = nodes.get("root_nodes", [])
    repairs = []
    unresolved = []

    def make_intermediate_id(path):
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")
        return f"Intermediate_{cleaned}"

    for missing_path in missing_paths:
        matches = [
            node for node in intermediate_nodes
            if _is_probable_pair(missing_path, _normalize_file_path(node.get("file_path", "")))
        ]
        parent_root = ""
        reason = ""
        unique_parents = sorted({node.get("parent_root") for node in matches if node.get("parent_root")})
        if len(unique_parents) == 1:
            parent_root = unique_parents[0]
            reason = "matched existing header/source sibling"
        elif len(root_nodes) == 1 and root_nodes[0].get("id"):
            parent_root = root_nodes[0].get("id")
            reason = "single-root repository"

        file_data = full_ir.get("files", {}).get(missing_path, {})
        if not parent_root and len(unique_parents) > 1 and not _file_has_executable_definitions(file_data):
            for candidate_parent in unique_parents:
                intermediate_nodes.append({
                    "id": make_intermediate_id(f"{candidate_parent}_{missing_path}"),
                    "parent_root": candidate_parent,
                    "file_path": missing_path,
                    "semantic_name": "Auto-mounted shared declaration file",
                    "description": (
                        "Automatically attached during RPG validation because Phase 1 "
                        "parsed this declaration/header file but the LLM omitted it. "
                        "The file has no executable function definitions, so attaching "
                        "it to multiple candidate roots preserves file completeness "
                        "without expanding Phase 3A function candidates."
                    ),
                })
                repairs.append((missing_path, candidate_parent, "shared declaration/header file"))
            continue

        if not parent_root:
            unresolved.append({
                "file_path": missing_path,
                "candidate_parent_roots": unique_parents,
            })
            continue

        intermediate_nodes.append({
            "id": make_intermediate_id(missing_path),
            "parent_root": parent_root,
            "file_path": missing_path,
            "semantic_name": "Auto-mounted implementation file",
            "description": (
                "Automatically attached during RPG validation because Phase 1 "
                f"parsed this file but the LLM omitted it; parent inferred by {reason}."
            ),
        })
        repairs.append((missing_path, parent_root, reason))

    if repairs:
        print(f"{prefix}   🛠️ [RPG完整性修复] 已挂载 {len(repairs)} 个 Phase 1 文件。")
        for path, parent, reason in repairs:
            print(f"{prefix}      - {path} -> {parent} ({reason})")

    if unresolved:
        raise ValueError(
            "RPG omitted Phase 1 files and their parent roots could not be inferred uniquely: "
            f"{json.dumps(unresolved, ensure_ascii=False)}"
        )

    return rpg_data


def _normalize_edge_relation_type(relation_type, default_type):
    """
    Keep RPG edge relation types in a small, stable vocabulary.

    This is intentionally conservative: it normalizes obvious variants but does
    not pretend to infer semantic truth that the RPG did not provide.
    """
    raw = str(relation_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "call": "calls",
        "function_call": "calls",
        "direct_call": "calls",
        "use": "uses_type",
        "uses": "uses_type",
        "type_use": "uses_type",
        "type_dependency": "uses_type",
        "dependency": "dependency",
        "depends_on": "dependency",
        "dataflow": "data_flow",
        "data_flow": "data_flow",
        "reexport": "facade_export",
        "re_export": "facade_export",
        "public_api": "facade_export",
        "facade": "facade_export",
        "facade_export": "facade_export",
        "implementation": "implementation_dependency",
        "implementation_dependency": "implementation_dependency",
        "internal_utility": "shared_internal_utility",
        "shared_internal_utility": "shared_internal_utility",
        "execution": "execution_order",
        "execution_order": "execution_order",
        "include_order": "execution_order",
    }
    return aliases.get(raw, default_type)


def validate_and_normalize_rpg_edges(rpg_data, prefix=""):
    """
    Validate edge endpoints and normalize coarse relation labels.

    Python can verify structural facts about the RPG graph: whether an edge
    points to existing nodes and whether intra-module edges stay inside a root.
    It cannot prove cross-language semantic equivalence here, so semantic
    completion remains a later 3A decision with explicit audit metadata.
    """
    nodes = rpg_data.get("nodes", {}) if isinstance(rpg_data, dict) else {}
    root_ids = {node.get("id") for node in nodes.get("root_nodes", []) if node.get("id")}
    intermediate_nodes = nodes.get("intermediate_nodes", [])
    intermediate_ids = {node.get("id") for node in intermediate_nodes if node.get("id")}
    intermediate_parent = {
        node.get("id"): node.get("parent_root")
        for node in intermediate_nodes
        if node.get("id")
    }
    edges = rpg_data.setdefault("edges", {})
    edge_validation = {
        "inter_module_edges": {"total": 0, "normalized_relation_types": 0, "dropped_self_loops": 0},
        "intra_module_edges": {
            "total": 0,
            "normalized_relation_types": 0,
            "dropped_self_loops": 0,
            "rolled_up_cross_root_edges": 0,
        },
    }

    normalized_inter_edges = []
    unresolved = []
    for edge in edges.get("inter_module_edges", []) or []:
        source = edge.get("source")
        target = edge.get("target")
        edge_validation["inter_module_edges"]["total"] += 1
        if source == target:
            edge_validation["inter_module_edges"]["dropped_self_loops"] += 1
            continue
        if source not in root_ids or target not in root_ids:
            unresolved.append({
                "edge_kind": "inter_module_edges",
                "source": source,
                "target": target,
                "missing": [
                    endpoint for endpoint, valid in ((source, source in root_ids), (target, target in root_ids))
                    if not valid
                ],
            })
            continue
        before = edge.get("relation_type")
        after = _normalize_edge_relation_type(before, "dependency")
        if before != after:
            edge_validation["inter_module_edges"]["normalized_relation_types"] += 1
        edge["relation_type"] = after
        normalized_inter_edges.append(edge)

    normalized_intra_edges = []
    rolled_up_inter_edges = []
    for edge in edges.get("intra_module_edges", []) or []:
        source = edge.get("source")
        target = edge.get("target")
        edge_validation["intra_module_edges"]["total"] += 1
        if source == target:
            edge_validation["intra_module_edges"]["dropped_self_loops"] += 1
            continue
        if source not in intermediate_ids or target not in intermediate_ids:
            unresolved.append({
                "edge_kind": "intra_module_edges",
                "source": source,
                "target": target,
                "missing": [
                    endpoint for endpoint, valid in ((source, source in intermediate_ids), (target, target in intermediate_ids))
                    if not valid
                ],
            })
            continue
        source_parent = intermediate_parent.get(source)
        target_parent = intermediate_parent.get(target)
        if source_parent != target_parent:
            if source_parent in root_ids and target_parent in root_ids and source_parent != target_parent:
                rolled_up_inter_edges.append({
                    "source": source_parent,
                    "target": target_parent,
                    "relation_type": _normalize_edge_relation_type(edge.get("relation_type"), "dependency"),
                    "description": (
                        "Rolled up from a cross-root intra_module_edges entry emitted by the model: "
                        f"{source} -> {target}. {edge.get('description', '')}"
                    ).strip(),
                    "evidence": edge.get("evidence", ""),
                })
                edge_validation["intra_module_edges"]["rolled_up_cross_root_edges"] += 1
                continue
            unresolved.append({
                "edge_kind": "intra_module_edges",
                "source": source,
                "target": target,
                "reason": "intra_module_edge_crosses_root",
                "source_parent_root": source_parent,
                "target_parent_root": target_parent,
            })
            continue
        before = edge.get("relation_type")
        after = _normalize_edge_relation_type(before, "execution_order")
        if before != after:
            edge_validation["intra_module_edges"]["normalized_relation_types"] += 1
        edge["relation_type"] = after
        normalized_intra_edges.append(edge)

    if unresolved:
        raise ValueError(
            "RPG contains invalid edge endpoints or illegal intra-root edges: "
            f"{json.dumps(unresolved, ensure_ascii=False)}"
        )

    seen_inter_edges = {
        (
            edge.get("source"),
            edge.get("target"),
            edge.get("relation_type"),
            edge.get("description"),
            edge.get("evidence"),
        )
        for edge in normalized_inter_edges
    }
    for edge in rolled_up_inter_edges:
        key = (
            edge.get("source"),
            edge.get("target"),
            edge.get("relation_type"),
            edge.get("description"),
            edge.get("evidence"),
        )
        if key in seen_inter_edges:
            continue
        seen_inter_edges.add(key)
        normalized_inter_edges.append(edge)

    edges["inter_module_edges"] = normalized_inter_edges
    edges["intra_module_edges"] = normalized_intra_edges
    metadata = rpg_data.setdefault("metadata", {})
    metadata["edge_validation"] = edge_validation

    normalized_count = (
        edge_validation["inter_module_edges"]["normalized_relation_types"]
        + edge_validation["intra_module_edges"]["normalized_relation_types"]
    )
    dropped_self_loops = (
        edge_validation["inter_module_edges"]["dropped_self_loops"]
        + edge_validation["intra_module_edges"]["dropped_self_loops"]
    )
    if normalized_count or dropped_self_loops:
        print(
            f"{prefix}   🧭 [RPG边校验] 归一化 {normalized_count} 个 relation_type，"
            f"丢弃 {dropped_self_loops} 条自环边。"
        )

    return rpg_data

# def auto_mount_leaf_nodes(rpg_data, full_ir):
#     """
#     【索引挂载机制】
#     作为 Phase 3 评估指标的纯粹路由指针。
#     剔除所有大模型脑补或正则生成的语义描述，只保留阶段一 schema 的原生物理标识与签名。
#     """
#     if "nodes" not in rpg_data:
#         rpg_data["nodes"] = {}
    
#     # 初始化/覆盖 leaf_nodes
#     rpg_data["nodes"]["leaf_nodes"] = []
    
#     inter_nodes = rpg_data["nodes"].get("intermediate_nodes", [])

#     for inter_node in inter_nodes:
#         file_path = inter_node.get("file_path")
#         if not file_path:
#             continue

#         # 从完整 IR 中获取该文件的 AST 数据
#         file_ast = full_ir.get("files", {}).get(file_path, {})
#         inter_id = inter_node.get("id", "Unknown_Inter")

#         # 1. 挂载独立函数 (C / C++ standalone / Rust standalone)
#         standalone_funcs = file_ast.get("functions", []) + file_ast.get("standalone_functions", [])
#         for func in standalone_funcs:
#             func_name = func.get("name", "unnamed")
#             rpg_data["nodes"]["leaf_nodes"].append({
#                 "id": f"Leaf_{func_name}",
#                 "parent_intermediate": inter_id,
#                 "ir_reference": f"functions.{func_name}",
#                 "node_subtype": "standalone_function",
#                 "name": func_name,
#                 "original_signature": func.get("signature", "")
#             })

#         # 2. 挂载类/结构体方法 (C++ classes / Rust impl_blocks)
#         class_blocks = file_ast.get("classes", []) + file_ast.get("impl_blocks", [])
#         for cls in class_blocks:
#             target_name = cls.get("name") or cls.get("target_type") or "UnknownClass"
#             for method in cls.get("methods", []):
#                 method_name = method.get("name", "unnamed")
#                 rpg_data["nodes"]["leaf_nodes"].append({
#                     "id": f"Leaf_{target_name}_{method_name}",
#                     "parent_intermediate": inter_id,
#                     "ir_reference": f"classes.{target_name}.{method_name}",
#                     "node_subtype": "member_function",
#                     "belongs_to_class": target_name,
#                     "name": method_name,
#                     "original_signature": method.get("signature", "")
#                 })

#         # 3. 挂载 Trait 实现方法 (Rust 特有)
#         for trt in file_ast.get("traits", []):
#             trait_name = trt.get("name", "UnknownTrait")
#             for method in trt.get("provided_methods", []):
#                 method_name = method.get("name", "unnamed")
#                 rpg_data["nodes"]["leaf_nodes"].append({
#                     "id": f"Leaf_trait_{trait_name}_{method_name}",
#                     "parent_intermediate": inter_id,
#                     "ir_reference": f"traits.{trait_name}.{method_name}",
#                     "node_subtype": "trait_method",
#                     "belongs_to_class": trait_name,
#                     "name": method_name,
#                     "original_signature": method.get("signature", "")
#                 })

#     return rpg_data

def phase_two_agent_workflow(full_ir, prompt_2a, llm_client, repo_name="", temperature=0.0):
    """
    执行完整的阶段二工作流：动态生成 RPG 图谱。
    """
    prefix = f"[{repo_name}] " if repo_name else ""
    
    print(f"{prefix}[Step 1] 开始进行 schema 脱水...")
    skeleton_ir = create_ir_skeleton(full_ir)
    
    # === 阶段 2A: RPG 图谱动态构建 (The Agent Loop) ===
    messages = [
        {"role": "system", "content": prompt_2a},
        {"role": "user", "content": f"这是目标仓库的 IR 骨架：\n{json.dumps(skeleton_ir, ensure_ascii=False)}"}
    ]
    
    rpg_json_str = None
    max_loops = 8 # 最大询问循环次数
    loop_count = 0
    
    print(f"{prefix}[Step 2A] 进入 RPG 架构师思考循环...")
    while loop_count < max_loops:
        loop_count += 1
        print(f"{prefix}   -> 第 {loop_count} 轮交互推理中...")
        
        response = llm_client.chat_completion(messages, temperature=temperature)
        messages.append({"role": "assistant", "content": response}) 
        
        # 1. 尝试拦截 <action>
        action_str = extract_xml_tag(response, "action")
        if action_str:
            print(f"{prefix}   ⚠️ 拦截到源码请求指令！开始检索源码...")
            try:
                action_data = clean_and_parse_json(action_str)
                if action_data.get("action") == "require_bodies":
                    requested_nodes = action_data.get("nodes", [])
                    fetched_bodies = fetch_requested_bodies(full_ir, requested_nodes)
                    
                    # 将提取到的源码补充给大模型
                    feedback_msg = f"系统已为你补充你请求的节点源码：\n{json.dumps(fetched_bodies, ensure_ascii=False)}\n请继续你的建图推理。"
                    messages.append({"role": "user", "content": feedback_msg})
                    continue # 继续下一轮循环
            except json.JSONDecodeError:
                messages.append({"role": "user", "content": "你的 <action> JSON 格式有误，请修复后重新输出。"})
                continue
                
        # 2. 尝试提取 <output>
        output_str = extract_xml_tag(response, "output")
        if output_str:
            try:
                # Fail early while the LLM conversation is still alive. This lets
                # the architect repair malformed JSON instead of ending Phase 2
                # with an unusable RPG.
                clean_and_parse_json(output_str)
                rpg_json_str = output_str
                print(f"{prefix}   ✅ RPG 拓扑图架构推理完成！跳出循环。")
                break
            except Exception as e:
                print(f"{prefix}   ⚠️ RPG <output> JSON 解析失败，要求模型修复: {e}")
                messages.append({
                    "role": "user",
                    "content": (
                        "你刚才的 <output> 内容不是合法 JSON，无法解析。"
                        "请只修复 JSON 语法，保持相同 RPG 语义，并重新在 <output> 标签中输出完整合法 JSON。"
                        f"解析错误: {e}"
                    )
                })
                continue
            
        # 3. 异常处理：既没有 action 也没有 output
        messages.append({"role": "user", "content": "请务必在 <action> 或 <output> 标签中输出结果。"})

    if not rpg_json_str:
        # 【死锁拦截调试信息】
        print("\n" + "!"*60)
        print(f"❌ [死锁拦截] {prefix} 架构师陷入死循环，未输出 <output>！")
        print("【大模型第 5 轮 (最后一轮) 的完整原始回复】:")
        print(response) # 打印它最后一次到底说了什么
        print("!"*60 + "\n")
        
        raise Exception("❌ RPG 构建失败：达到最大循环次数或解析异常。")

    # === 【后处理清洗】物理切断所有自环边 ===
    try:
        temp_rpg_data = clean_and_parse_json(rpg_json_str)
        if "edges" in temp_rpg_data and "intra_module_edges" in temp_rpg_data["edges"]:
            original_edges = temp_rpg_data["edges"]["intra_module_edges"]
            # 列表推导式：只保留 source 和 target 不相等的边
            cleaned_edges = [edge for edge in original_edges if edge.get("source") != edge.get("target")]
            
            if len(original_edges) != len(cleaned_edges):
                print(f"{prefix}   🛡️ [架构修正] 已自动拦截并切断 {len(original_edges) - len(cleaned_edges)} 条非法的模块内自环边！")
            
            temp_rpg_data["edges"]["intra_module_edges"] = cleaned_edges
            # 将清洗后的干净数据转回 JSON 字符串
            rpg_json_str = json.dumps(temp_rpg_data, ensure_ascii=False)
    except Exception as e:
        print(f"{prefix}   ⚠️ [架构修正警告] JSON 解析失败，跳过自环清理: {e}")

    # # === 解析大模型输出的图谱，并执行核心增强：自动挂载 Leaf Nodes ===
    # try:
    #     rpg_data = clean_and_parse_json(rpg_json_str) 
        
    #     # 【自动挂载机制核心触发】：在这里用 Python 将底层的 AST 函数全量塞进图谱里！
    #     rpg_data = auto_mount_leaf_nodes(rpg_data, full_ir)
    #     print(f"{prefix}   🔗 [自动挂载] 已成功将原生函数的 AST 数据结构挂载至中间节点！")
        
    # except Exception as e:
    #     print("\n" + "="*60)
    #     print("❌ [调试拦截] RPG 图谱 (Step 2A) JSON 解析失败！")
    #     print(f"报错信息: {e}")
    #     print("-" * 60)
    #     print("【提取出的 <output> 字符串原文 (用 repr 显示排版)】:")
    #     print(repr(rpg_json_str))
    #     print("="*60 + "\n")
    #     raise e

    # === 解析大模型输出的图谱，并执行核心增强：自动挂载 Leaf Nodes ===
    try:
        rpg_data = clean_and_parse_json(rpg_json_str)
        rpg_data = validate_and_repair_rpg_file_paths(rpg_data, full_ir, prefix=prefix)
        rpg_data = mount_missing_phase1_files(rpg_data, full_ir, prefix=prefix)
        rpg_data = validate_and_normalize_rpg_edges(rpg_data, prefix=prefix)
        print(f"{prefix}   🔗 [架构生成] RPG 图谱解析完毕，准备落盘 (Leaf Nodes 已精简)！")
    except Exception as e:
        print(f"{prefix}   ❌ [致命错误] 图谱 JSON 解析或路径校验失败: {e}")
        raise

    return rpg_data
