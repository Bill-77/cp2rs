import json
import os
from .prompts import PROMPT_3A_MACRO_MAPPER
# 复用我们在 Phase 2 写好的 LLM 客户端和解析工具
from rpg_builder.llm_client import LLMClient
from rpg_builder.agent_loop import extract_xml_tag, clean_and_parse_json

def evaluate_macro_alignment(source_rpg_path, target_rpg_path, output_report_path):
    """
    执行宏观功能点对齐评估。
    """
    print(f"   -> 📊 加载 RPG 图谱: {os.path.basename(source_rpg_path)} VS {os.path.basename(target_rpg_path)}")
    
    with open(source_rpg_path, 'r', encoding='utf-8') as f:
        source_rpg = json.load(f)
    with open(target_rpg_path, 'r', encoding='utf-8') as f:
        target_rpg = json.load(f)
        
    combined_input = {
        "source_rpg": source_rpg,
        "target_rpg": target_rpg
    }
    
    messages = [
        {"role": "system", "content": PROMPT_3A_MACRO_MAPPER},
        {"role": "user", "content": f"请对比以下两个仓库的 RPG 索引：\n{json.dumps(combined_input, ensure_ascii=False)}"}
    ]
    
    llm = LLMClient()
    print(f"   -> 🧠 裁判大模型正在进行架构同构性评估 (Macro Alignment)...")
    
    # 评测任务需要极高的稳定性，保持低温
    response = llm.chat_completion(messages, temperature=0.1) 
    
    output_str = extract_xml_tag(response, "output")
    if not output_str:
        print("❌ 大模型输出异常，未找到 <output> 标签，请查看原始日志。")
        print("【原始输出】:\n", response)
        return None
        
    try:
        alignment_report = clean_and_parse_json(output_str)
    except Exception as e:
        print(f"❌ 评测报告 JSON 解析失败: {e}")
        print("【提取的文本】:\n", output_str)
        return None
    
    # 保存报告
    os.makedirs(os.path.dirname(output_report_path), exist_ok=True)
    with open(output_report_path, 'w', encoding='utf-8') as f:
        json.dump(alignment_report, f, ensure_ascii=False, indent=2)
        
    score = alignment_report.get('macro_alignment_score', 'N/A')
    print(f"   ✅ [评估完成] 宏观功能对齐度得分: {score}/100")
    print(f"   -> 报告已保存至: {output_report_path}\n")
    
    return alignment_report