import re
import json
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

def phase_two_agent_workflow(full_ir, prompt_2a, llm_client, repo_name=""):
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
    max_loops = 5 # 最大询问循环次数
    loop_count = 0
    
    print(f"{prefix}[Step 2A] 进入 RPG 架构师思考循环...")
    while loop_count < max_loops:
        loop_count += 1
        print(f"{prefix}   -> 第 {loop_count} 轮交互推理中...")
        
        response = llm_client.chat_completion(messages) 
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
            rpg_json_str = output_str
            print(f"{prefix}   ✅ RPG 拓扑图架构推理完成！跳出循环。")
            break
            
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
        print(f"{prefix}   🔗 [架构生成] RPG 图谱解析完毕，准备落盘 (Leaf Nodes 已精简)！")
    except Exception as e:
        print(f"{prefix}   ❌ [致命错误] 图谱 JSON 解析彻底失败: {e}")

    return rpg_data
