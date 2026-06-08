"""
DeepSeek API 客户端

调用 DeepSeek Chat API 生成汉字书写指令。
API 兼容 OpenAI 格式，需要 DEEPSEEK_API_KEY 环境变量或在 GUI 中输入。
"""

import json
import os
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"


class DeepSeekClient:
    """DeepSeek API 客户端"""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or self._load_key_from_env() or self._load_key_from_file()
        self._requests = None

    @staticmethod
    def _load_key_from_env() -> str:
        return os.environ.get("DEEPSEEK_API_KEY", "")

    @staticmethod
    def _load_key_from_file() -> str:
        key_file = os.path.join(os.path.dirname(__file__), "apikey.txt")
        if not os.path.exists(key_file):
            return ""
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("sk-"):
                    return first_line
        except Exception:
            pass
        return ""

    def _ensure_requests(self):
        if self._requests is None:
            import requests
            self._requests = requests

    @property
    def api_key(self) -> str:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def chat(self, system_prompt: str, user_prompt: str,
             temperature: float = 0.3,
             max_tokens: int = 4096) -> Optional[str]:
        """调用 DeepSeek Chat API

        Args:
            system_prompt: 系统提示
            user_prompt: 用户输入
            temperature: 生成温度
            max_tokens: 最大生成 token 数

        Returns:
            AI 响应文本, 失败返回 None
        """
        if not self._api_key:
            logger.error("DeepSeek API key not configured")
            return None

        self._ensure_requests()

        url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            resp = self._requests.post(url, headers=headers, json=body, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logger.info(f"DeepSeek response: {len(content)} chars")
            return content
        except self._requests.exceptions.Timeout:
            logger.error("DeepSeek API timeout")
            return None
        except self._requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API error: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"DeepSeek response parse error: {e}")
            return None

    def generate_writing_instructions(self, prompt: str,
                                       temperature: float = 0.3) -> Optional[str]:
        """生成汉字书写指令

        Args:
            prompt: 完整 prompt (由 ai_instruction 模块构建)
            temperature: 生成温度

        Returns:
            AI 返回的 JSON 字符串
        """
        system_prompt = (
            "你是一个汉字书写机器人路径规划器。"
            "根据用户要求生成 XY 平台运动控制指令序列。"
            "只返回 JSON，不要加任何解释、代码块标记或额外文字。"
        )
        return self.chat(system_prompt, prompt, temperature=temperature)
