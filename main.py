import os
import json
import re
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

# 【新增】补丁(Phase 1.5): 轻量级跨文件符号链接器
def inject_global_references(repo_data):
    """
    扫描整个仓库的函数体源码，通过正则单词边界匹配，自动标定隐式数据流引用的全局状态。
    """
    # 1. 跨文件收集该仓库内所有的全局变量名称
    global_names = set()
    for file_path, file_data in repo_data.get("files", {}).items():
        for state in file_data.get("entities", {}).get("global_states", []):
            if state.get("name"):
                global_names.add(state["name"])

    if not global_names:
        return repo_data # 没有全局变量，直接返回

    # 2. 构建正则模式，严格匹配单词边界，防止类似 "count" 匹配到 "counter"
    pattern_str = r'\b(' + '|'.join(re.escape(name) for name in global_names) + r')\b'
    regex = re.compile(pattern_str)

    # 3. 跨文件扫描所有函数和方法，寻找全局符号引用
    for file_path, file_data in repo_data.get("files", {}).items():
        # 扫描 standalone_functions
        for func in file_data.get("entities", {}).get("standalone_functions", []):
            body = func.get("body", "")
            if body:
                matches = set(regex.findall(body))
                if matches:
                    func["referenced_global_states"] = list(matches)

        # 扫描 behaviors 中的类方法
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
    # 提取文件夹名称作为仓库名
    repo_name = os.path.basename(os.path.normpath(repo_path))
    
    # 1. 智能语言嗅探
    detected_language = detect_repo_language(repo_path)
    
    if detected_language == "unknown":
        print(f"⚠️ 无法识别仓库 [{repo_name}] 的语言，已跳过。")
        return None
    
    # 2. 构建符合蓝图要求的全局大字典
    repo_data = {
        "repository_name": repo_name,
        "language": detected_language,  # 动态打上语言标签
        "files": {}
    }
    
    # 3. 根据语言自动选择解析器和合法后缀
    if detected_language == "rust":
        parser = RustParser()
        valid_extensions = {'.rs'}
    else:
        parser = CppParser()
        valid_extensions = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'}
    
    print(f"🚀 开始扫描仓库: {repo_path} (自动识别为: {detected_language.upper()} 语言)")
    
    # 4. 递归遍历目录，过滤合法后缀
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                # 获取绝对路径和相对路径
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)  # 相对路径作为 JSON 中的唯一 Key
                
                # 读取二进制文件内容 (避免换行符编码问题)
                try:
                    with open(full_path, 'rb') as f:
                        code_bytes = f.read()
                except Exception as e:
                    print(f"❌ 读取文件失败 {rel_path}: {e}")
                    continue
                
                print(f"  -> 正在解析: {rel_path} ...")
                
                # 5. 调用解析器并将结果挂载到全局字典 (保持独立)
                file_result = parser.parse_file_content(rel_path, code_bytes)
                repo_data["files"][rel_path] = file_result
                
    # 【新增】6. 当整个仓库的所有文件都解析完毕后，执行 Phase 1.5 跨文件符号链接补丁！
    print(f"  -> 正在执行 Phase 1.5: 跨文件全局符号关联扫描...")
    repo_data = inject_global_references(repo_data)
    return repo_data

if __name__ == "__main__":
    # 配置输入目录（同时支持 C/C++ 和 Rust 仓库）
    BASE_INPUT_DIRS = ["data/cc_repos", "data/rust_repos"]   
    BASE_OUTPUT_DIR = "output/parsed_repos"
    
    # 确保输出目录存在
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    
    # 遍历所有输入目录
    for base_dir in BASE_INPUT_DIRS:
        if not os.path.exists(base_dir):
            print(f"⚠️ 找不到目录 {base_dir}，跳过...")
            continue
        
        # 遍历当前输入目录下的所有仓库
        repo_names = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        if not repo_names:
            continue
        
        print(f"\n🔎 在 {base_dir} 中发现 {len(repo_names)} 个仓库: {repo_names}")
        
        # 逐个解析仓库
        for repo_name in repo_names:
            target_repo_path = os.path.join(base_dir, repo_name)
            
            # 执行全仓库解析 (内部会自动嗅探语言)
            final_json_data = parse_repository(target_repo_path)
            if not final_json_data:
                continue
            
            # 将该仓库的结果独立保存为 JSON 文件
            output_filename = f"{repo_name}_parsed.json"
            output_path = os.path.join(BASE_OUTPUT_DIR, output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_json_data, f, indent=2, ensure_ascii=False)
                
            print(f"✅ 仓库 [{repo_name}] 解析完成！(共 {len(final_json_data['files'])} 个文件) -> {output_path}")
            print("-" * 50)
            
    print("\n🎉 所有仓库批量解析完毕！第一阶段数据提取完成！")