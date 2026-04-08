import json
import copy

import copy

def create_ir_skeleton(full_ir):
    """
    将完整的 IR 脱水，剔除所有的物理代码体 (body/declaration)，生成供 LLM 初始阅读的骨架。
    """
    skeleton_ir = copy.deepcopy(full_ir)
    
    files_dict = skeleton_ir.get("files", {})
    for file_path, file_data in files_dict.items():
        entities = file_data.get("entities", {})

        # 脱水: data_models
        for model in entities.get("data_models", []):
            model.pop("declaration", None)

        # 脱水: macros
        for macro in entities.get("macros", []):
            macro.pop("body", None)

        # 脱水: standalone_functions
        for func in entities.get("standalone_functions", []):
            func.pop("body", None)

        # 脱水: behaviors (类/结构体方法)
        for behavior in entities.get("behaviors", []):
            for method in behavior.get("methods", []):
                method.pop("body", None)

    return skeleton_ir

def fetch_requested_bodies(full_ir, ir_references):
    """
    根据大模型提供的 ir_references 列表，从完整的 IR 中精准捞取对应的源码，增加对 global_states 的支持。
    """
    retrieved_data = {}
    entities = full_ir.get("entities", {})

    for ref in ir_references:
        parts = ref.split('.')
        category = parts[0]
        try:
            if category == "standalone_functions" and len(parts) == 2:
                for func in entities.get("standalone_functions", []):
                    if func.get("name") == parts[1]:
                        retrieved_data[ref] = func.get("body", "Body not found")
                        break
            elif category == "behaviors" and len(parts) == 3:
                for behavior in entities.get("behaviors", []):
                    if behavior.get("target_entity") == parts[1]:
                        for method in behavior.get("methods", []):
                            if method.get("name") == parts[2]:
                                retrieved_data[ref] = method.get("body", "Body not found")
                                break
            # 【新增】对全局状态声明的索取支持
            elif category == "global_states" and len(parts) == 2:
                for gs in entities.get("global_states", []):
                    if gs.get("name") == parts[1]:
                        retrieved_data[ref] = gs.get("declaration", "Declaration not found")
                        break
        except Exception as e:
            retrieved_data[ref] = f"Error retrieving {ref}: {str(e)}"
            
    return retrieved_data