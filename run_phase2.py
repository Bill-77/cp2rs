import os
import json
import concurrent.futures
import threading
import argparse

from rpg_builder.prompts import get_architect_prompt
from rpg_builder.agent_loop import phase_two_agent_workflow
from rpg_builder.llm_client import LLMClient

# 配置路径
INPUT_DIR = "output/parsed_repos"
RPG_OUTPUT_DIR = "output/rpg_graphs"

print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def process_single_repo(filename, llm_client):
    repo_name = filename.replace("_parsed.json", "")
    input_path = os.path.join(INPUT_DIR, filename)
    
    safe_print(f"\n🚀 [{repo_name}] 任务已分配至线程，开始构建 RPG 图谱...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        full_ir = json.load(f)
        
    try:
        # 动态获取语言并拦截非法 Prompt
        repo_lang = full_ir.get("language", "unknown")
        safe_print(f"   -> 🔍 识别到 [{repo_name}] 的语言标签为: '{repo_lang}'")
        
        active_prompt_2a = get_architect_prompt(repo_lang)

        results = phase_two_agent_workflow(
            full_ir=full_ir,
            prompt_2a=active_prompt_2a,
            llm_client=llm_client,
            repo_name=repo_name 
        )
        
        # 安全提取图谱
        rpg_data = results.get("rpg_graph", results) if isinstance(results, dict) else results

        rpg_path = os.path.join(RPG_OUTPUT_DIR, f"{repo_name}_rpg.json")
        with open(rpg_path, 'w', encoding='utf-8') as f:
            json.dump(results["rpg_graph"], f, ensure_ascii=False, indent=2)
                        
        safe_print(f"🎉 [{repo_name}]RPG 图谱生成成功！产物已保存。")
        
    except Exception as e:
        safe_print(f"❌ [{repo_name}] 处理失败: {str(e)}")

def main():
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="CP2RS Phase 2 (仅生成 RPG 图谱)")
    parser.add_argument("-r", "--repo", type=str, default="",
                        help="指定要处理的仓库名 (例如: cJSON)")
    args = parser.parse_args()

    os.makedirs(RPG_OUTPUT_DIR, exist_ok=True)
    
    llm = LLMClient() 
    tasks = [f for f in os.listdir(INPUT_DIR) if f.endswith("_parsed.json")]
    
    # 按仓库名进行过滤
    if args.repo:
        tasks = [f for f in tasks if args.repo.lower() in f.lower()]

    if not tasks:
        print(f"⚠️ 没有找到需要处理的 _parsed.json 文件 (过滤条件: {args.repo}).")
        return

    print(f"📦 根据过滤条件，发现 {len(tasks)} 个仓库任务，准备启动并发处理...")

    max_concurrency = min(len(tasks), 10)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        futures = [executor.submit(process_single_repo, filename, llm) for filename in tasks]
        concurrent.futures.wait(futures)
        
    print("\n✅ 所有 RPG 图谱生成任务执行完毕！")

if __name__ == "__main__":
    main()