import os
import json
import concurrent.futures
import threading
from rpg_builder.prompts import PROMPT_2A_ARCHITECT, PROMPT_2B_EXTRACTOR
from rpg_builder.agent_loop import phase_two_agent_workflow
from rpg_builder.llm_client import LLMClient

# 配置路径
INPUT_DIR = "output/parsed_repos"
RPG_OUTPUT_DIR = "output/rpg_graphs"
FP_OUTPUT_DIR = "output/function_points"

# 创建一个打印锁，防止多线程并发打印时控制台字符错乱穿插
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    """线程安全的打印函数"""
    with print_lock:
        print(*args, **kwargs)

def process_single_repo(filename, llm_client):
    """处理单个仓库的核心逻辑，供线程池调用"""
    repo_name = filename.replace("_parsed.json", "")
    input_path = os.path.join(INPUT_DIR, filename)
    
    safe_print(f"\n🚀 [{repo_name}] 任务已分配至线程，开始构建 RPG 与功能清单...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        full_ir = json.load(f)
        
    try:
        # 启动智能体工作流 (传入 repo_name 用于日志前缀区分)
        results = phase_two_agent_workflow(
            full_ir=full_ir,
            prompt_2a=PROMPT_2A_ARCHITECT,
            prompt_2b=PROMPT_2B_EXTRACTOR,
            llm_client=llm_client,
            repo_name=repo_name # [新增] 传递仓库名
        )
        
        # 落盘产物 A: RPG 图谱
        rpg_path = os.path.join(RPG_OUTPUT_DIR, f"{repo_name}_rpg.json")
        with open(rpg_path, 'w', encoding='utf-8') as f:
            json.dump(results["rpg_graph"], f, ensure_ascii=False, indent=2)
            
        # 落盘产物 B: 降维功能清单
        fp_path = os.path.join(FP_OUTPUT_DIR, f"{repo_name}_function_points.json")
        with open(fp_path, 'w', encoding='utf-8') as f:
            json.dump(results["function_point_table"], f, ensure_ascii=False, indent=2)
            
        safe_print(f"🎉 [{repo_name}] 阶段二处理成功！产物已保存。")
        
    except Exception as e:
        safe_print(f"❌ [{repo_name}] 处理失败: {str(e)}")

def main():
    # 确保输出目录存在
    os.makedirs(RPG_OUTPUT_DIR, exist_ok=True)
    os.makedirs(FP_OUTPUT_DIR, exist_ok=True)
    
    # 初始化大模型客户端 (通常 LLM SDK 的客户端是线程安全的，如果报错可以改到 process_single_repo 里初始化)
    llm = LLMClient() 
    
    # 收集需要处理的文件
    tasks = [f for f in os.listdir(INPUT_DIR) if f.endswith("_parsed.json")]
    
    if not tasks:
        print("没有找到需要处理的 _parsed.json 文件。")
        return

    print(f"📦 发现 {len(tasks)} 个仓库任务，准备启动并发处理...")

    # 使用线程池并发执行 (max_workers 可根据你的 API 并发限制调整，一般设为 5 或 10)
    max_concurrency = min(len(tasks), 10)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        # 提交所有任务到线程池
        futures = [executor.submit(process_single_repo, filename, llm) for filename in tasks]
        
        # 等待所有任务完成
        concurrent.futures.wait(futures)
        
    print("\n✅ 所有阶段二并发任务执行完毕！")

if __name__ == "__main__":
    main()