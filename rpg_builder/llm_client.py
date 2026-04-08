import os
from openai import OpenAI

class LLMClient:
    def __init__(self, api_key=None, model="deepseek-chat"):
        """
        初始化 DeepSeek LLM 客户端。
        推荐设置环境变量 DEEPSEEK_API_KEY。
        """
        # 优先使用传入的 api_key，如果没有则去环境变量取
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("未找到 API Key！请在环境变量中设置 DEEPSEEK_API_KEY，或在初始化时传入。")
        
        self.model = model
        
        # DeepSeek API 的官方 Base URL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1"
        )

    def chat_completion(self, messages, temperature=0.1):
        """
        调用 DeepSeek API 进行对话。
        
        Args:
            messages: 消息列表，格式为 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            temperature: 采样温度。架构推演需要极高的逻辑严密性和 JSON 格式稳定性，建议保持在 0.1 以下。
            
        Returns:
            str: 模型返回的文本内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                # 模型能返回的最大长度
                max_tokens=8192,
                top_p=0.95
            )
            return response.choices[0].message.content
            
        except Exception as e:
            # 在外层调度器 Agent Loop 中统一处理异常，这里直接向上抛出
            raise RuntimeError(f"DeepSeek API 调用失败: {str(e)}")