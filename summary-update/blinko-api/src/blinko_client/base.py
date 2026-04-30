import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

import requests
from dotenv import load_dotenv


@dataclass
class BlinkoConfig:
    base_url: str
    api_key: str


class BlinkoBaseClient:
    """Blinko API 基础客户端类"""

    def __init__(self, config: BlinkoConfig):
        self.base_url = config.base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/v1"
        self.headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """统一请求方法"""
        url = f"{self.api_base}{endpoint}"
        response = self._session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json: Optional[Dict] = None) -> Dict[str, Any]:
        return self._request("POST", endpoint, json=json)

    def patch(self, endpoint: str, json: Optional[Dict] = None) -> Dict[str, Any]:
        return self._request("PATCH", endpoint, json=json)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        return self._request("DELETE", endpoint)


def get_project_env_path() -> Path:
    """
    获取项目根目录 .env 路径

    Returns:
        项目根目录 .env 文件路径
    """
    return Path(__file__).resolve().parents[4] / ".env"


def load_config(env_file: Optional[Path] = None) -> BlinkoConfig:
    """
    从环境变量加载配置

    Args:
        env_file: 可选的环境变量文件路径；默认使用项目根目录 .env

    Returns:
        Blinko 配置对象
    """
    if env_file is None:
        env_file = get_project_env_path()
    load_dotenv(env_file)

    base_url = os.getenv("BLINKO_BASE_URL", "http://47.103.50.106:1111")
    api_key = os.getenv("BLINKO_API_KEY", "")

    if not api_key:
        raise ValueError(f"BLINKO_API_KEY is required in env file: {env_file}")

    return BlinkoConfig(base_url=base_url, api_key=api_key)
