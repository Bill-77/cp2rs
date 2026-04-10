import os
import json
import re

# 导入刚刚封板的终级 C 语言解析器
from parsers.c_parser import CParser
# 保留原有解析器（假设尚未重构完毕）
from parsers.cpp_parser import CppParser
from parsers.rust_parser import RustParser

def detect_repo_language(repo_path):
    """
    嗅探仓库的主要语言类型
    返回: 'rust', 'cpp', 'c', 或 'unknown'
    """
    cxx_extensions = {'.cpp', '.cc', '.cxx', '.hpp'}
    has_c = False
    
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            # 只要有 .rs 就是 Rust 仓库
            if ext == '.rs':
                return "rust"  
            # 只要有 C++ 专属后缀就是 C++
            if ext in cxx_extensions:
                return "cpp"
            if ext in {'.c', '.h'}:
                has_c = True
                
    return "c" if has_c else "unknown"

def inject_global_references(repo_data):
    """
    【旧版补偿逻辑】：跨文件符号关联扫描。
    注意：此函数仅对尚未重构的 C++ 和 Rust 解析器生效。
    """
    # 【架构级拦截】：保护 Schema 3.1 的精确度
    if repo_data.get("language") == "c":
        print("  -> [架构提示] C 语言已启用底层 AST 数据流引擎，无需进行正则补偿，避免破坏 Scope Stack 的精准度。")
        return repo_data

    # ======== 以下为针对旧版 Schema 的正则补偿逻辑 ========
    global_names = set()
    for file_path, file_data in repo_data.get("files", {}).items():
        for state in file_data.get("entities", {}).get("global_states", []):
            if state.get("name"):
                global_names.add(state["name"])

    if not global_names:
        return repo_data

    pattern_str = r'\b(' + '|'.join(re.escape(name) for name in global_names) + r')\b'
    regex = re.compile(pattern_str)

    for file_path, file_data in repo_data.get("files", {}).items():
        for func in file_data.get("entities", {}).get("standalone_functions", []):
            body = func.get("body", "")
            if body:
                matches = set(regex.findall(body))
                if matches:
                    func["referenced_global_states"] = list(matches)

        for behavior in file_data.get("entities", {}).get("behaviors", []):
            for method in behavior.get("methods", []):
                body = method.get("body", "")
                if body:
                    matches = set(regex.findall(body))
                    if matches:
                        method["referenced_global_states"] = list(matches)

    return repo_data

def parse_repository(repo_path):
    """
    遍历整个代码仓库，智能判断语言并解析，合并为单一的扁平化字典。
    """
    repo_name = os.path.basename(os.path.normpath(repo_path))
    detected_language = detect_repo_language(repo_path)
    
    if detected_language == "unknown":
        print(f"⚠️ 无法识别仓库 [{repo_name}] 的语言，已跳过。")
        return None
    
    repo_data = {
        "repository_name": repo_name,
        "language": detected_language,
        "files": {}
    }
    
    # 根据语言自动选择解析器和合法后缀
    if detected_language == "rust":
        parser = RustParser()
        valid_extensions = {'.rs'}
    elif detected_language == "cpp":
        parser = CppParser()
        valid_extensions = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'}
    elif detected_language == "c":
        # 【新增】：路由至全新的 CParser
        parser = CParser()
        valid_extensions = {'.c', '.h'}
    
    print(f"🚀 开始扫描仓库: {repo_path} (自动识别为: {detected_language.upper()} 语言)")
    
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path).replace("\\", "/") # 统一路径分隔符
                
                try:
                    with open(full_path, 'rb') as f:
                        code_bytes = f.read()
                except Exception as e:
                    print(f"❌ 读取文件失败 {rel_path}: {e}")
                    continue
                
                print(f"  -> 正在解析: {rel_path} ...")
                
                # 【接口适配】：调用全新的 parse_file 接口
                if detected_language == "c":
                    file_result = parser.parse_file(rel_path, code_bytes)
                else:
                    # 兼容老版解析器的接口
                    file_result = parser.parse_file_content(rel_path, code_bytes) 
                    
                repo_data["files"][rel_path] = file_result
                
    # 全局关联分析
    print(f"  -> 正在执行 Phase 1.5: 跨文件全局符号关联扫描...")
    repo_data = inject_global_references(repo_data)
    
    return repo_data

if __name__ == "__main__":
    BASE_INPUT_DIRS = ["data/cc_repos", "data/rust_repos"]   
    BASE_OUTPUT_DIR = "output/parsed_repos"
    
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    
    for base_dir in BASE_INPUT_DIRS:
        if not os.path.exists(base_dir):
            print(f"⚠️ 找不到目录 {base_dir}，跳过...")
            continue
        
        repo_names = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        if not repo_names:
            continue
        
        print(f"\n🔎 在 {base_dir} 中发现 {len(repo_names)} 个仓库: {repo_names}")
        
        for repo_name in repo_names:
            target_repo_path = os.path.join(base_dir, repo_name)
            
            final_json_data = parse_repository(target_repo_path)
            if not final_json_data:
                continue
            
            output_filename = f"{repo_name}_parsed.json"
            output_path = os.path.join(BASE_OUTPUT_DIR, output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_json_data, f, indent=2, ensure_ascii=False)
                
            print(f"✅ 仓库 [{repo_name}] 解析完成！(共 {len(final_json_data['files'])} 个文件) -> {output_path}")
            print("-" * 50)
            
    print("\n🎉 所有仓库批量解析完毕！第一阶段数据提取完成！")