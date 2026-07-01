import os
import json
import argparse

# 导入所有终极解析器
from parsers.c_parser import CParser
from parsers.cpp_parser import CppParser
from parsers.rust_parser import RustParser

IGNORE_DIRS = {
    'test', 'tests', 'testing', 
    'example', 'examples', 'sample', 'samples',
    'benchmark', 'benchmarks', 'benches',
    'fuzz', 'fuzzer', 'fuzzing',
    'doc', 'docs', 
    'third_party', 'vendor', 'extern', 'deps',
    'build', 'out', 'target', 'bin'
}

TEST_DIR_MARKERS = {
    "test", "tests", "testing", "unittest", "unittests",
    "testcase", "testcases", "testrunner", "fuzz", "fuzzer", "fuzzing",
}

TEST_FILE_STEMS = {
    "test", "tests", "unittest", "unit_test", "main_test",
    "fuzz", "fuzzer", "fuzz_main",
}

def is_ignored_dir(dirname):
    """Phase 1/2 focus on repository implementation semantics, not test/fuzz/example code."""
    lower = dirname.lower()
    if lower.startswith(".") or lower in IGNORE_DIRS:
        return True
    if lower in TEST_DIR_MARKERS:
        return True
    if any(marker in lower for marker in ("test_", "_test", "tests_", "_tests", "testrunner", "fuzz")):
        return True
    if lower.startswith(("test", "unittest", "bench", "fuzz")):
        return True
    if lower.endswith(("test", "tests", "testing", "benchmark", "benchmarks", "fuzzer")):
        return True
    return False

def is_ignored_source_file(filename):
    """Filter test/fuzz source files that are outside obvious test directories."""
    lower = filename.lower()
    stem, ext = os.path.splitext(lower)
    if ext not in {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.rs'}:
        return False
    if stem in TEST_FILE_STEMS:
        return True
    if stem.startswith(("test_", "tests_", "fuzz_", "fuzzer_")):
        return True
    if stem.endswith(("_test", "_tests", "_unittest", "_fuzzer", "_fuzz")):
        return True
    return False

def dehydrate(data):
    """
    【数据脱水算法】
    递归剔除所有空列表 []、空字典 {}、空字符串 "" 和 None。
    极大地压缩 JSON 体积，减少大模型 Token 消耗并提高注意力集中度。
    """
    if isinstance(data, dict):
        return {
            k: dehydrate(v) 
            for k, v in data.items() 
            if v not in ([], "", {}, None)
        }
    elif isinstance(data, list):
        return [
            dehydrate(item) 
            for item in data 
            if item not in ([], "", {}, None)
        ]
    return data

def detect_repo_language(repo_path):
    """
    嗅探仓库的主要语言类型
    返回: 'rust', 'cpp', 'c', 或 'unknown'
    """
    cxx_extensions = {'.cpp', '.cc', '.cxx', '.hpp'}
    has_c = False
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not is_ignored_dir(d)]
        for file in files:
            if is_ignored_source_file(file):
                continue
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

def parse_repository(repo_path, pre_detected_lang=None):
    """
    遍历整个代码仓库，智能判断语言并解析，合并为单一的扁平化字典。
    """
    repo_name = os.path.basename(os.path.normpath(repo_path))
    # 如果外层已经探测过，就直接用，否则自行探测
    detected_language = pre_detected_lang if pre_detected_lang else detect_repo_language(repo_path)
    
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
        parser = CParser()
        valid_extensions = {'.c', '.h'}
    
    print(f"🚀 开始扫描仓库: {repo_path} (自动识别为: {detected_language.upper()} 语言)")
    
    for root, dirs, files in os.walk(repo_path):
        # 【降噪 1：目录级拦截】
        # 就地修改 dirs 列表，过滤掉黑名单目录和隐藏目录（如 .git, .github）
        # os.walk 就不会再进入这些被剔除的目录了！
        dirs[:] = [d for d in dirs if not is_ignored_dir(d)]

        for file in files:
            # 【降噪 2：文件级拦截】
            # 过滤掉散落在正常目录下的测试/模糊测试文件 (如 *_test.c, test_*.rs, fuzz_main.c)
            if is_ignored_source_file(file):
                continue

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
                
                # 【接口统一】：三门语言的引擎现已全部对齐 parse_file 接口
                try:
                    file_result = parser.parse_file(rel_path, code_bytes)
                    repo_data["files"][rel_path] = file_result
                except Exception as e:
                    print(f"❌ 解析语法树失败 {rel_path}: {e}")
                
    return repo_data

if __name__ == "__main__":
    # ==========================================
    # 命令行测试脚手架配置
    # ==========================================
    parser = argparse.ArgumentParser(description="多语言 AST 全量解析引擎 (C/C++/Rust)")
    parser.add_argument("-l", "--lang", choices=["all", "c", "cpp", "rust"], default="all",
                        help="按语言过滤：只解析特定语言的仓库")
    parser.add_argument("-r", "--repo", type=str, default="",
                        help="按仓库名过滤：只解析名字包含该字符串的仓库 (例如: venus_engine)")
    
    args = parser.parse_args()

    BASE_INPUT_DIRS = ["data/cc_repos", "data/rust_repos"]   
    BASE_OUTPUT_DIR = "output/parsed_repos"
    
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print(f"🛠️  AST 解析引擎已启动")
    print(f"📌 当前过滤条件 -> 语言: [{args.lang}], 仓库名: [{args.repo if args.repo else '全部'}]")
    print("=" * 60)

    for base_dir in BASE_INPUT_DIRS:
        if not os.path.exists(base_dir):
            continue
        
        repo_names = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        if not repo_names:
            continue
        
        for repo_name in repo_names:
            # 按仓库名称过滤 (支持模糊匹配)
            if args.repo and args.repo.lower() not in repo_name.lower():
                continue
                
            target_repo_path = os.path.join(base_dir, repo_name)
            
            # 提前探测语言
            detected_lang = detect_repo_language(target_repo_path)
            
            # 按语言类型过滤
            if args.lang != "all" and detected_lang != args.lang:
                print(f"⏩ 跳过仓库 [{repo_name}] (语言为 {detected_lang}，但不符合过滤条件 {args.lang})")
                continue

            # 开始正式解析
            final_json_data = parse_repository(target_repo_path, pre_detected_lang=detected_lang)
            if not final_json_data or not final_json_data["files"]:
                continue
            
            output_filename = f"{repo_name}_parsed.json"
            output_path = os.path.join(BASE_OUTPUT_DIR, output_filename)
            
            # 执行脱水算法
            cleaned_json_data = dehydrate(final_json_data)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_json_data, f, indent=2, ensure_ascii=False)
                
            print(f"✅ 仓库 [{repo_name}] 解析完成！(共 {len(final_json_data['files'])} 个文件) -> {output_path}")
            print("-" * 50)
            
    print("\n🎉 所有仓库批量解析完毕！第一阶段数据提取完成！")
