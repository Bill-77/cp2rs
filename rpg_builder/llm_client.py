import os
import time
from openai import OpenAI

class LLMClient:
    ENV_FILES = (".env.local", ".env")

    def __init__(self, api_key=None, model="deepseek-v4-flash"):
        """
        初始化 DeepSeek LLM 客户端。
        推荐设置环境变量 DEEPSEEK_API_KEY；如果当前进程没有继承环境变量，
        会退回读取项目根目录下的 .env.local / .env。
        """
        # 优先使用传入的 api_key，如果没有则去环境变量取
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or self._load_api_key_from_env_files()
        if not self.api_key:
            raise ValueError("未找到 API Key！请在环境变量中设置 DEEPSEEK_API_KEY、在项目 .env/.env.local 中配置，或在初始化时传入。")
        
        self.model = model
        self.last_usage = {}
        self.usage_totals = {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 0,
            "elapsed_seconds": 0.0,
        }
        
        # DeepSeek API 的官方 Base URL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

    def chat_completion(self, messages, temperature=0.1, model=None, max_tokens=8192):
        """
        调用 DeepSeek API 进行对话。
        
        Args:
            messages: 消息列表，格式为 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            temperature: 采样温度。架构推演需要极高的逻辑严密性和 JSON 格式稳定性，建议保持在 0.1 以下。
            model: 模型名称，可选。
            max_tokens: 模型返回的最大长度。

        Returns:
            str: 模型返回的文本内容
        """
        try:
            started = time.monotonic()
            response = self.client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature,
                # 模型能返回的最大长度
                max_tokens=max_tokens,
                top_p=0.95
            )
            elapsed = time.monotonic() - started
            usage = getattr(response, "usage", None)
            self.last_usage = {
                "model": getattr(response, "model", None) or model or self.model,
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
                "cache_hit_tokens": int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0),
                "cache_miss_tokens": int(getattr(usage, "prompt_cache_miss_tokens", 0) or 0),
                "elapsed_seconds": round(elapsed, 3),
                "reported_by_api": usage is not None,
            }
            self.usage_totals["calls"] += 1
            for key in (
                "prompt_tokens", "completion_tokens", "total_tokens",
                "cache_hit_tokens", "cache_miss_tokens",
            ):
                self.usage_totals[key] += self.last_usage[key]
            self.usage_totals["elapsed_seconds"] = round(
                self.usage_totals["elapsed_seconds"] + elapsed,
                3,
            )
            return response.choices[0].message.content
            
        except Exception as e:
            # 在外层调度器 Agent Loop 中统一处理异常，这里直接向上抛出
            raise RuntimeError(f"DeepSeek API 调用失败: {str(e)}")

    def get_usage_stats(self):
        return {
            "last_usage": dict(self.last_usage),
            "totals": dict(self.usage_totals),
        }

    def _load_api_key_from_env_files(self):
        for filename in self.ENV_FILES:
            path = os.path.join(os.getcwd(), filename)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        if key.strip() != "DEEPSEEK_API_KEY":
                            continue
                        value = value.strip().strip('"').strip("'")
                        if value:
                            return value
            except OSError:
                continue
        return None
