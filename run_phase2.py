import os
import json
import concurrent.futures
import threading
from rpg_builder.prompts import PROMPT_2B_EXTRACTOR, get_architect_prompt
from rpg_builder.agent_loop import phase_two_agent_workflow
from rpg_builder.llm_client import LLMClient

# 配置路径
INPUT_DIR = "output/parsed_repos"
RPG_OUTPUT_DIR = "output/rpg_graphs"
FP_OUTPUT_DIR = "output/function_points"

print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def process_single_repo(filename, llm_client):
    repo_name = filename.replace("_parsed.json", "")
    input_path = os.path.join(INPUT_DIR, filename)
    
    safe_print(f"\n🚀 [{repo_name}] 任务已分配至线程，开始构建 RPG 与功能清单...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        full_ir = json.load(f)
        
    try:
        # 【核心修复】：动态获取语言并拦截非法 Prompt
        repo_lang = full_ir.get("language", "unknown")
        safe_print(f"   -> 🔍 识别到 [{repo_name}] 的语言标签为: '{repo_lang}'")
        
        active_prompt_2a = get_architect_prompt(repo_lang)
        if not isinstance(active_prompt_2a, str) or len(active_prompt_2a) < 50:
            raise ValueError(f"获取到的 Prompt 无效！当前语言: {repo_lang}")
            
        results = phase_two_agent_workflow(
            full_ir=full_ir,
            prompt_2a=active_prompt_2a,
            prompt_2b=PROMPT_2B_EXTRACTOR,
            llm_client=llm_client,
            repo_name=repo_name 
        )
        
        rpg_path = os.path.join(RPG_OUTPUT_DIR, f"{repo_name}_rpg.json")
        with open(rpg_path, 'w', encoding='utf-8') as f:
            json.dump(results["rpg_graph"], f, ensure_ascii=False, indent=2)
            
        fp_path = os.path.join(FP_OUTPUT_DIR, f"{repo_name}_function_points.json")
        with open(fp_path, 'w', encoding='utf-8') as f:
            json.dump(results["function_point_table"], f, ensure_ascii=False, indent=2)
            
        safe_print(f"🎉 [{repo_name}] 阶段二处理成功！产物已保存。")
        
    except Exception as e:
        safe_print(f"❌ [{repo_name}] 处理失败: {str(e)}")

def main():
    os.makedirs(RPG_OUTPUT_DIR, exist_ok=True)
    os.makedirs(FP_OUTPUT_DIR, exist_ok=True)
    
    llm = LLMClient() 
    tasks = [f for f in os.listdir(INPUT_DIR) if f.endswith("_parsed.json")]
    
    if not tasks:
        print("没有找到需要处理的 _parsed.json 文件。")
        return

    print(f"📦 发现 {len(tasks)} 个仓库任务，准备启动并发处理...")

    max_concurrency = min(len(tasks), 10)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        futures = [executor.submit(process_single_repo, filename, llm) for filename in tasks]
        concurrent.futures.wait(futures)
        
    print("\n✅ 所有阶段二并发任务执行完毕！")

if __name__ == "__main__":
    main()