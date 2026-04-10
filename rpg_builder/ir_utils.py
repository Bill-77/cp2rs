import json
import copy

def create_ir_skeleton(full_ir):
    """
    将完整的 IR 脱水，剔除所有的物理代码体，生成供 LLM 初始阅读的骨架。
    """
    skeleton_ir = copy.deepcopy(full_ir)
    
    for file_path, file_data in skeleton_ir.get("files", {}).items():
        # === 适配最新 Schema 3.1 ===
        for func in file_data.get("functions", []):
            func.pop("body", None)
        for macro in file_data.get("macros", []):
            macro.pop("definition", None)
        for t in file_data.get("types", []):
            t.pop("declaration", None) # 减少认知负担
            
        # === 兼容老版本 CPP/Rust (防报错) ===
        if "entities" in file_data:
            entities = file_data["entities"]
            for func in entities.get("standalone_functions", []):
                func.pop("body", None)
            for behavior in entities.get("behaviors", []):
                for method in behavior.get("methods", []):
                    method.pop("body", None)

    return skeleton_ir

def fetch_requested_bodies(full_ir, ir_references):
    """
    精确捞取源码，完全适配扁平化 C Parser 输出。
    """
    retrieved_data = {}

    for ref in ir_references:
        parts = ref.split('.')
        if len(parts) < 2:
            retrieved_data[ref] = "Invalid path format. Expected category.name"
            continue
            
        category = parts[0]
        entity_name = parts[1]
        found = False
        
        try:
            for file_path, file_data in full_ir.get("files", {}).items():
                # 新架构直接查顶层分类
                if category in ["functions", "global_states", "types", "macros"]:
                    for item in file_data.get(category, []):
                        if item.get("name") == entity_name:
                            if category == "functions":
                                retrieved_data[ref] = item.get("body", "Body not found")
                            elif category == "macros":
                                retrieved_data[ref] = item.get("definition", "Definition not found")
                            else:
                                retrieved_data[ref] = item.get("declaration", "Declaration not found")
                            found = True
                            break
                if found:
                    break
                    
            if not found:
                retrieved_data[ref] = "Node Not Found in any file."
                
        except Exception as e:
            retrieved_data[ref] = f"Error retrieving {ref}: {str(e)}"
            
    return retrieved_data