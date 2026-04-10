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
    根据大模型提供的 ir_references 列表，从完整的 IR 中精准捞取对应的源码。
    """
    retrieved_data = {}

    for ref in ir_references:
        parts = ref.split('.')
        category = parts[0]
        found = False
        
        try:
            # 【修复点】：遍历所有文件，在各自的 entities 里面寻找目标
            for file_path, file_data in full_ir.get("files", {}).items():
                entities = file_data.get("entities", {})
                
                if category == "standalone_functions" and len(parts) == 2:
                    for func in entities.get("standalone_functions", []):
                        if func.get("name") == parts[1]:
                            retrieved_data[ref] = func.get("body", "Body not found")
                            found = True
                            break
                elif category == "behaviors" and len(parts) == 3:
                    for behavior in entities.get("behaviors", []):
                        if behavior.get("target_entity") == parts[1]:
                            for method in behavior.get("methods", []):
                                if method.get("name") == parts[2]:
                                    retrieved_data[ref] = method.get("body", "Body not found")
                                    found = True
                                    break
                # 寻找全局变量声明
                elif category == "global_states" and len(parts) == 2:
                    for gs in entities.get("global_states", []):
                        if gs.get("name") == parts[1]:
                            retrieved_data[ref] = gs.get("declaration", "Declaration not found")
                            found = True
                            break
                
                if found:
                    break # 如果在这个文件里找到了，就停止遍历其他文件

            # 防死锁提示：如果真没找到，明确告诉大模型，别让它猜
            if not found:
                retrieved_data[ref] = "Node Not Found in any file."

        except Exception as e:
            retrieved_data[ref] = f"Error retrieving {ref}: {str(e)}"
            
    return retrieved_data