import re
import json
from .ir_utils import create_ir_skeleton, fetch_requested_bodies

def extract_xml_tag(text, tag_name):
    """工具函数：利用正则表达式提取 XML 标签内的内容"""
    pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None

# 对付脏字符和格式错位的工具函数
def clean_and_parse_json(json_str):
    """清洗不间断空格等非法字符，并尝试暴力提取 JSON {} 或 []"""
    if not json_str:
        raise ValueError("传入的 JSON 字符串为空")
        
    # 1. 净化特殊空格 (\xa0 等)
    clean_text = json_str.replace('\xa0', ' ').replace('\u200b', '').strip()
    
    # 2. 尝试直接解析
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        # 3. 终极回退机制：暴力寻找最外层的 {} (字典) 或 [] (列表)
        start_dict, end_dict = clean_text.find('{'), clean_text.rfind('}')
        start_list, end_list = clean_text.find('['), clean_text.rfind(']')
        
        # 判断是字典结构还是列表结构在最外层
        if start_dict != -1 and end_dict != -1 and (start_list == -1 or start_dict < start_list):
            target_str = clean_text[start_dict : end_dict + 1]
        elif start_list != -1 and end_list != -1:
            target_str = clean_text[start_list : end_list + 1]
        else:
            raise ValueError("无法在字符串中找到有效的 {} 或 [] 结构。")
            
        return json.loads(target_str)

def phase_two_agent_workflow(full_ir, prompt_2a, prompt_2b, llm_client, repo_name=""):
    """
    执行完整的阶段二工作流：先动态生成 RPG 图谱，再降维生成功能清单。
    """
    prefix = f"[{repo_name}] " if repo_name else ""
    
    print(f"{prefix}[Step 1] 开始进行 IR 脱水...")
    skeleton_ir = create_ir_skeleton(full_ir)
    
    # === 阶段 2A: RPG 图谱动态构建 (The Agent Loop) ===
    messages = [
        {"role": "system", "content": prompt_2a},
        {"role": "user", "content": f"这是目标仓库的 IR 骨架：\n{json.dumps(skeleton_ir, ensure_ascii=False)}"}
    ]
    
    rpg_json_str = None
    max_loops = 5 # 最大询问循环次数
    loop_count = 0
    
    print(f"{prefix}[Step 2A] 进入 RPG 架构师思考循环...")
    while loop_count < max_loops:
        loop_count += 1
        print(f"{prefix}   -> 第 {loop_count} 轮交互推理中...")
        
        response = llm_client.chat_completion(messages) 
        messages.append({"role": "assistant", "content": response}) 
        
        # 1. 尝试拦截 <action>
        action_str = extract_xml_tag(response, "action")
        if action_str:
            print(f"{prefix}   ⚠️ 拦截到源码请求指令！开始检索源码...")
            try:
                action_data = clean_and_parse_json(action_str)
                if action_data.get("action") == "require_bodies":
                    requested_nodes = action_data.get("nodes", [])
                    fetched_bodies = fetch_requested_bodies(full_ir, requested_nodes)
                    
                    # 将提取到的源码补充给大模型
                    feedback_msg = f"系统已为你补充你请求的节点源码：\n{json.dumps(fetched_bodies, ensure_ascii=False)}\n请继续你的建图推理。"
                    messages.append({"role": "user", "content": feedback_msg})
                    continue # 继续下一轮循环
            except json.JSONDecodeError:
                messages.append({"role": "user", "content": "你的 <action> JSON 格式有误，请修复后重新输出。"})
                continue
                
        # 2. 尝试提取 <output>
        output_str = extract_xml_tag(response, "output")
        if output_str:
            rpg_json_str = output_str
            print(f"{prefix}   ✅ RPG 拓扑图构建成功！跳出循环。")
            break
            
        # 3. 异常处理：既没有 action 也没有 output
        messages.append({"role": "user", "content": "请务必在 <action> 或 <output> 标签中输出结果。"})

    if not rpg_json_str:
        raise Exception("❌ RPG 构建失败：达到最大循环次数或解析异常。")

    # === 阶段 2B: 降维功能清单提取 (One-Shot) ===
    print(f"{prefix}[Step 2B] 开始将 RPG 降维提炼为 Root 级功能清单...")
    
    messages_2b = [
        {"role": "system", "content": prompt_2b},
        {"role": "user", "content": f"这是刚刚构建完毕的 RPG 拓扑图数据：\n{rpg_json_str}"}
    ]
    
    response_2b = llm_client.chat_completion(messages_2b)
    function_point_table_str = extract_xml_tag(response_2b, "output")
    
    if not function_point_table_str:
        raise Exception("❌ 功能清单提炼失败：未找到 <output> 标签。")

    print(f"{prefix}   ✅ 功能清单提炼成功！")
    
    # === 调试版解析：看看大模型不稳定的回复具体什么情况，打印案发现场，先不自动修复 ===
    try:
        rpg_data = clean_and_parse_json(rpg_json_str) 
    except Exception as e:
        print("\n" + "="*60)
        print("❌ [调试拦截] RPG 图谱 (Step 2A) JSON 解析失败！")
        print(f"报错信息: {e}")
        print("-" * 60)
        print("【提取出的 <output> 字符串原文 (用 repr 显示排版)】:")
        print(repr(rpg_json_str))
        print("="*60 + "\n")
        raise e

    try:
        fp_data = clean_and_parse_json(function_point_table_str)
    except Exception as e:
        print("\n" + "="*60)
        print("❌ [调试拦截] 功能清单 (Step 2B) JSON 解析失败！")
        print(f"报错信息: {e}")
        print("-" * 60)
        print("【大模型 Step 2B 完整的原始回复】:")
        print(response_2b)
        print("-" * 60)
        print("【提取出的 <output> 字符串原文 (用 repr 显示排版)】:")
        print(repr(function_point_table_str))
        print("="*60 + "\n")
        raise e

    return {
        "rpg_graph": rpg_data,
        "function_point_table": fp_data
    }