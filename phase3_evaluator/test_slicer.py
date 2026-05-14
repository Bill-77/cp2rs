import os
import json
import re

def _extract_test_blocks(file_content, target_func_base_name):
    """
    内部辅助函数：纯文本暴力解析器，提取包含目标函数调用的 #[test] 代码块
    """
    tests_found = []
    # 匹配 #[test] 及其下方的 fn 定义
    pattern = re.compile(r'#\[test\]\s*(?:#\[.*?\]\s*)*(?:pub\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*\{')
    
    for match in pattern.finditer(file_content):
        test_name = match.group(1)
        start_idx = match.start()
        body_start_idx = match.end() - 1 # '{' 的位置
        
        brace_count = 0
        in_string = False
        in_char = False
        escape_next = False
        end_idx = -1
        
        # 括号匹配算法切出完整函数体
        for i in range(body_start_idx, len(file_content)):
            char = file_content[i]
            
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not in_char:
                in_string = not in_string
            elif char == "'" and not in_string:
                in_char = not in_char
                
            if not in_string and not in_char:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
                        
        if end_idx != -1:
            raw_source = file_content[start_idx:end_idx]
            # 只有当测试源码中真正调用了目标函数，才认为这是一个有效的测试用例
            # 比如 json::parse，测试里可能写的是 parse("...") 
            if re.search(rf'\b{target_func_base_name}\s*\(', raw_source):
                tests_found.append({
                    "test_name": test_name,
                    "source_code": raw_source
                })
                
    return tests_found

def discover_physical_tests(answer_repo_path, answer_function):
    """
    【SOP 第 1 关：测试淘金】
    直接遍历答案仓库的 src/ 和 tests/ 物理目录，寻找测试用例源码。
    """
    found_tests = []
    # 如果目标函数是 json::parse，我们在源码里找的时候重点看 "parse"
    base_func_name = answer_function.split("::")[-1]
    
    # 遍历整个答案仓库，重点是 src 和 tests 目录
    for root, dirs, files in os.walk(answer_repo_path):
        for file in files:
            if file.endswith(".rs"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # 如果文件里连 base_func_name 都没有，直接跳过，加速处理
                    if base_func_name not in content or "#[test]" not in content:
                        continue
                        
                    blocks = _extract_test_blocks(content, base_func_name)
                    for block in blocks:
                        block["file_path"] = os.path.relpath(file_path, answer_repo_path)
                        found_tests.append(block)
                except Exception as e:
                    print(f"读取文件 {file_path} 时出错: {e}")
                    
    return found_tests

def extract_precise_dependencies(trans_schema_path, trans_func_name):
    """
    【SOP 第 2 关：依赖精准提纯】
    从翻译仓库的 Phase 1 Schema 中，精准提取目标函数的签名和所需的结构体/全局变量。
    """
    with open(trans_schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
        
    context = {
        "target_signature": "",
        "dependencies": {
            "types": [],
            "globals": []
        }
    }
    
    target_node = None
    target_type_name = None  # 记录该函数所属的结构体名称 (破解 Self 隐身)
    
    # 1. 寻找目标函数节点
    for file_path, file_data in schema.get("files", {}).items():
        for func in file_data.get("standalone_functions", []):
            if func.get("name") == trans_func_name:
                target_node = func
                break
        
        if not target_node:
            for cls in file_data.get("impl_blocks", []):
                for method in cls.get("methods", []):
                    if method.get("name") == trans_func_name:
                        target_node = method
                        target_type_name = cls.get("target_type")  # 抓取所属结构体名！
                        break
                if target_node: break
        if target_node: break
            
    if not target_node:
        return context  # 没找到函数，返回空
        
    context["target_signature"] = target_node.get("signature", "")
    reads_globals = target_node.get("data_flow", {}).get("reads_globals", [])
    
    # 提取签名中的单词，用于匹配类型 (例如 "pub fn parse(s: &str) -> Result<JsonValue, Error>" 提取出 Result, JsonValue, Error)
    sig_words = set(re.findall(r'[a-zA-Z_]\w*', context["target_signature"]))
    
    # 如果函数在 impl 块里，强制把结构体名字加入搜索字典
    if target_type_name:
        sig_words.add(target_type_name)

    # 2. 精准提取依赖的 Types 和 Global States
    for file_path, file_data in schema.get("files", {}).items():
        # 提取相关类型 (只提取在签名中出现过的自定义类型，避免塞爆上下文)
        for t in file_data.get("types", []):
            if t.get("name") in sig_words:
                context["dependencies"]["types"].append(t)
                
        # 提取相关全局变量 (只提取 data_flow.reads_globals 里记录的)
        for g in file_data.get("global_states", []):
            if g.get("name") in reads_globals:
                context["dependencies"]["globals"].append(g)
                
    return context