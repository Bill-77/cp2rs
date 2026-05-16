import json
import copy

def create_ir_skeleton(full_ir):
    """
    【升级版】将完整的 schema 脱水，剔除所有的物理代码体和行号，
    生成供 Phase 2 LLM 初始阅读的骨架 (RPG 蓝图)。
    完全兼容 Schema 4.x (C / C++ / Rust)。
    """
    skeleton_ir = copy.deepcopy(full_ir)
    
    def strip_heavy_fields(func_dict):
        """通用脱水器：剥离一切不需要大模型在宏观阶段阅读的重型字段"""
        if not isinstance(func_dict, dict): return
        func_dict.pop("body", None)
        func_dict.pop("start_line", None)
        func_dict.pop("end_line", None)
        func_dict.pop("initializer_list_snapshot", None) # 针对 C++
    
    for file_path, file_data in skeleton_ir.get("files", {}).items():
        # 1. 处理扁平函数 (C 语言及顶层函数)
        for func in file_data.get("functions", []):
            strip_heavy_fields(func)
        for func in file_data.get("standalone_functions", []):
            strip_heavy_fields(func)
            
        # 2. 处理 C++ 类内部方法
        for cls in file_data.get("classes", []):
            for method in cls.get("methods", []):
                strip_heavy_fields(method)
                
        # 3. 处理 Rust Impl 块和 Trait 默认方法
        for impl in file_data.get("impl_blocks", []):
            for method in impl.get("methods", []):
                strip_heavy_fields(method)
        for trait in file_data.get("traits", []):
            for method in trait.get("provided_methods", []):
                strip_heavy_fields(method)

        # 4. 剥离宏定义和长篇类型声明
        for macro in file_data.get("macros", []):
            macro.pop("definition", None)
        for t in file_data.get("types", []):
            t.pop("declaration", None) 

    return skeleton_ir


def fetch_requested_bodies(full_ir, ir_references):
    """
    【升级版】按需精确捞取源码，完全适配多层级复杂 Schema。
    支持格式：
    - 平铺级： "functions.cJSON_Parse"
    - 嵌套级： "classes.TcpSocket.methods.connect"
    - Rust级： "impl_blocks.Parser.methods.bump"
    """
    retrieved_data = {}

    for ref in ir_references:
        parts = ref.split('.')
        if len(parts) < 2:
            retrieved_data[ref] = "Invalid path format. Expected at least category.name"
            continue
            
        category = parts[0]
        found = False
        
        try:
            for file_path, file_data in full_ir.get("files", {}).items():
                
                # --- 场景 A: 平铺结构 (C 函数, 宏, 类型) ---
                if len(parts) == 2:
                    entity_name = parts[1]
                    for item in file_data.get(category, []):
                        if item.get("name") == entity_name:
                            if category in ["functions", "standalone_functions"]:
                                retrieved_data[ref] = item.get("body", "Body not found")
                            elif category == "macros":
                                retrieved_data[ref] = item.get("definition", "Definition not found")
                            else:
                                retrieved_data[ref] = item.get("declaration", "Declaration not found")
                            found = True
                            break
                            
                # --- 场景 B: 嵌套结构 (C++ 类方法, Rust Impl 方法) ---
                elif len(parts) == 4:
                    parent_name = parts[1] # "TcpSocket" 或 "Parser"
                    sub_category = parts[2] # "methods"
                    entity_name = parts[3] # "connect"
                    
                    for parent_item in file_data.get(category, []):
                        # C++ 是 "name", Rust impl 可能是 "target_type", 兼顾处理
                        p_name = parent_item.get("name") or parent_item.get("target_type")
                        if p_name == parent_name:
                            for item in parent_item.get(sub_category, []):
                                if item.get("name") == entity_name:
                                    retrieved_data[ref] = item.get("body", "Body not found")
                                    found = True
                                    break
                        if found: break
                
                if found: break
                    
            if not found:
                retrieved_data[ref] = "Node Not Found in any file."
                
        except Exception as e:
            retrieved_data[ref] = f"Error retrieving {ref}: {str(e)}"
            
    return retrieved_data