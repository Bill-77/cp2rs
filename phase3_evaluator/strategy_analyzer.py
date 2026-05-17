import json
from rpg_builder.llm_client import LLMClient
from .prompts import PROMPT_STRATEGY_ANALYSIS

class StrategyAnalyzer:
    """
    CP2RS Phase 3: 战略透视分析器 (仅在场景二触发)
    用于对比 Target 与 Answer 之间的翻译策略差异。
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_strategy_report(self, tgt_ans_report_path: str) -> dict:
        """读取 Tgt vs Ans 的 3A 报告，生成战略透视报告"""
        print("\n" + "="*50)
        print("🧠 [Phase 3 Strategy] 启动目标与人类标杆的战略透视对比分析...")
        
        with open(tgt_ans_report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        metrics = json.dumps(report_data.get("quantitative_metrics", {}), indent=2)
        
        # 提取模块映射摘要，避免传入过大的完整代码体
        modules_summary = []
        for mod in report_data.get("aligned_modules", []):
            summary = f"Target Module [{mod['src_module']}] 映射到 Answer Module [{mod['tgt_module']}]"
            summary += f"\n  - 微观对齐了 {len(mod.get('aligned_functions', []))} 个等价逻辑函数。"
            modules_summary.append(summary)
            
        prompt = PROMPT_STRATEGY_ANALYSIS.format(
            quantitative_metrics=metrics,
            aligned_modules_summary="\n".join(modules_summary)
        )
        
        messages = [{"role": "user", "content": prompt}]
        try:
            reply = self.llm.chat_completion(messages, temperature=0.3)
            
            # 使用十六进制 ASCII 规避 UI 渲染 Bug
            reply = reply.strip()
            if reply.startswith("\x60\x60\x60json"): 
                reply = reply[7:]
            if reply.startswith("\x60\x60\x60"): 
                reply = reply[3:]
            if reply.endswith("\x60\x60\x60"): 
                reply = reply[:-3]
            
            return json.loads(reply.strip())
        except Exception as e:
            print(f"⚠️ 战略透视分析失败: {e}")
            return {"error": "Failed to generate strategy analysis."}