#!/usr/bin/env python3
"""
通知分发模块

功能：
1. 统一发送 Telegram 错误通知
2. 按配置发送 Telegram 成功日志
3. 按配置发送 Telegram / WeChat 成功结果
"""

import asyncio
import json
import os
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from utils.summary_uploader import get_env_bool, load_env, upload_to_wechat

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MESSAGE_LIMIT = 3500


def _get_telegram_target() -> Optional[Dict[str, str]]:
    """
    获取 Telegram 主动推送目标

    Returns:
        包含 token 和 chat_id 的字典；未配置时返回 None
    """
    load_env()

    bot_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (
        os.getenv("TELEGRAM_NOTIFY_CHAT_ID")
        or os.getenv("TELEGRAM_USER_ID")
        or ""
    ).strip()

    if not bot_token or not chat_id:
        return None

    return {
        "bot_token": bot_token,
        "chat_id": chat_id,
    }


def split_telegram_message(text: str, max_length: int = TELEGRAM_MESSAGE_LIMIT) -> List[str]:
    """
    将长文本拆分为 Telegram 可发送的消息块

    Args:
        text: 原始文本
        max_length: 单条消息最大长度

    Returns:
        消息块列表
    """
    content = text.strip()
    if not content:
        return []

    chunks: List[str] = []
    remaining = content

    while len(remaining) > max_length:
        split_at = remaining.rfind("\n", 0, max_length)
        if split_at < max_length * 0.6:
            split_at = remaining.rfind(" ", 0, max_length)
        if split_at < max_length * 0.6:
            split_at = max_length

        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def send_telegram_message(text: str) -> bool:
    """
    主动发送 Telegram 消息

    Args:
        text: 消息内容

    Returns:
        是否发送成功
    """
    target = _get_telegram_target()
    if target is None:
        print("[跳过] 未配置 Telegram 主动推送目标")
        return False

    url = f"{TELEGRAM_API_BASE}/bot{target['bot_token']}/sendMessage"
    chunks = split_telegram_message(text)
    if not chunks:
        print("[跳过] Telegram 消息为空")
        return False

    try:
        for chunk in chunks:
            data = urllib.parse.urlencode(
                {
                    "chat_id": target["chat_id"],
                    "text": chunk,
                }
            ).encode("utf-8")

            request = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                result = json.loads(body)

            if not result.get("ok"):
                raise RuntimeError(result.get("description", "Telegram API 调用失败"))

        return True
    except Exception as exc:
        print(f"[错误] Telegram 主动推送失败: {exc}")
        return False


def _format_stage_icon(stage_value: Optional[str]) -> str:
    """
    将流程状态格式化为图标

    Args:
        stage_value: 状态值

    Returns:
        图标文本
    """
    if stage_value == "success":
        return "✅"
    if stage_value == "failed":
        return "❌"
    if stage_value == "skipped":
        return "⏭️"
    return "❓"


def _append_upload_lines(lines: List[str], upload_results: Optional[Dict]) -> None:
    """
    追加上传阶段摘要

    Args:
        lines: 输出行列表
        upload_results: 上传结果字典
    """
    if not isinstance(upload_results, dict):
        return

    labels = {
        "hiagent_rag": "HiAgent RAG",
        "lis_rss": "LIS-RSS",
        "memos": "Memos",
        "blinko": "Blinko",
        "wechat": "WeChat",
    }

    lines.append("上传结果:")
    for key, label in labels.items():
        if key in upload_results:
            lines.append(f"- {label}: {'✅' if upload_results.get(key) else '❌'}")


def build_error_message(
    title: str,
    reason: str,
    article_id: Optional[int] = None,
    source_name: Optional[str] = None,
    stages: Optional[Dict] = None,
) -> str:
    """
    构建错误通知消息

    Args:
        title: 文章标题
        reason: 失败原因
        article_id: 文章 ID
        source_name: 来源名称
        stages: 阶段状态

    Returns:
        格式化后的消息文本
    """
    lines = ["❌ 论文处理失败", f"标题: {title}"]

    if article_id:
        lines.append(f"文章ID: {article_id}")
    if source_name:
        lines.append(f"来源: {source_name}")

    lines.append("")
    lines.append(f"原因: {reason}")

    if stages:
        lines.append("")
        lines.append("阶段状态:")
        lines.append(f"- PDF下载: {_format_stage_icon(stages.get('pdf_download'))}")
        lines.append(f"- PDF验证: {_format_stage_icon(stages.get('pdf_validate'))}")
        lines.append(f"- PDF总结: {_format_stage_icon(stages.get('pdf_summary'))}")
        _append_upload_lines(lines, stages.get("upload"))

    return "\n".join(lines)


def build_success_log_message(
    title: str,
    article_id: int,
    source_name: Optional[str],
    stages: Optional[Dict],
) -> str:
    """
    构建成功日志消息

    Args:
        title: 文章标题
        article_id: 文章 ID
        source_name: 来源名称
        stages: 阶段状态

    Returns:
        格式化后的消息文本
    """
    lines = ["✅ 论文处理成功", f"标题: {title}"]

    if article_id > 0:
        lines.append(f"文章ID: {article_id}")
    if source_name:
        lines.append(f"来源: {source_name}")

    lines.append("")
    lines.append("阶段状态:")
    lines.append(f"- PDF下载: {_format_stage_icon(stages.get('pdf_download') if stages else None)}")
    lines.append(f"- PDF验证: {_format_stage_icon(stages.get('pdf_validate') if stages else None)}")
    lines.append(f"- PDF总结: {_format_stage_icon(stages.get('pdf_summary') if stages else None)}")

    if stages:
        _append_upload_lines(lines, stages.get("upload"))

    return "\n".join(lines)


def build_success_result_message(
    title: str,
    md_content: str,
    article_id: int,
    source_name: Optional[str],
) -> str:
    """
    构建成功结果消息

    Args:
        title: 文章标题
        md_content: 摘要正文
        article_id: 文章 ID
        source_name: 来源名称

    Returns:
        格式化后的结果消息
    """
    lines = ["📄 论文总结结果", f"标题: {title}"]

    if article_id > 0:
        lines.append(f"文章ID: {article_id}")
    if source_name:
        lines.append(f"来源: {source_name}")

    lines.append("")
    lines.append(md_content.strip())

    return "\n".join(lines).strip()


def dispatch_error_notification(
    title: str,
    reason: str,
    article_id: Optional[int] = None,
    source_name: Optional[str] = None,
    stages: Optional[Dict] = None,
) -> bool:
    """
    发送错误通知

    Args:
        title: 文章标题
        reason: 失败原因
        article_id: 文章 ID
        source_name: 来源名称
        stages: 阶段状态

    Returns:
        是否成功发送
    """
    message = build_error_message(
        title=title,
        reason=reason,
        article_id=article_id,
        source_name=source_name,
        stages=stages,
    )
    return send_telegram_message(message)


async def dispatch_success_notifications(
    title: str,
    article_id: int,
    source_name: Optional[str],
    md_content: str,
    stages: Optional[Dict],
    config: Dict,
    allow_wechat: bool = True,
    force_wechat: bool = False,
) -> Dict[str, bool]:
    """
    按配置分发成功通知

    Args:
        title: 文章标题
        article_id: 文章 ID
        source_name: 来源名称
        md_content: 摘要正文
        stages: 阶段状态
        config: 工作流配置
        allow_wechat: 是否允许发送 WeChat
        force_wechat: 是否强制开启 WeChat

    Returns:
        各通知渠道发送结果
    """
    results = {
        "telegram_log": False,
        "telegram_result": False,
        "wechat": False,
    }

    if get_env_bool("PDF_SUMMARY_PUSH_TELEGRAM_LOG", False):
        results["telegram_log"] = send_telegram_message(
            build_success_log_message(
                title=title,
                article_id=article_id,
                source_name=source_name,
                stages=stages,
            )
        )

    if get_env_bool("PDF_SUMMARY_PUSH_TELEGRAM_RESULT", False):
        results["telegram_result"] = send_telegram_message(
            build_success_result_message(
                title=title,
                md_content=md_content,
                article_id=article_id,
                source_name=source_name,
            )
        )

    should_push_wechat = allow_wechat and (
        force_wechat or get_env_bool("PDF_SUMMARY_PUSH_WECHAT", False)
    )

    if should_push_wechat:
        results["wechat"] = await upload_to_wechat(
            md_content=md_content,
            article_id=article_id,
            article_title=title,
            source_name=source_name,
            config=config,
        )

    return results


def dispatch_success_notifications_sync(
    title: str,
    article_id: int,
    source_name: Optional[str],
    md_content: str,
    stages: Optional[Dict],
    config: Dict,
    allow_wechat: bool = True,
    force_wechat: bool = False,
) -> Dict[str, bool]:
    """
    同步分发成功通知

    Args:
        title: 文章标题
        article_id: 文章 ID
        source_name: 来源名称
        md_content: 摘要正文
        stages: 阶段状态
        config: 工作流配置
        allow_wechat: 是否允许发送 WeChat
        force_wechat: 是否强制开启 WeChat

    Returns:
        各通知渠道发送结果
    """
    return asyncio.run(
        dispatch_success_notifications(
            title=title,
            article_id=article_id,
            source_name=source_name,
            md_content=md_content,
            stages=stages,
            config=config,
            allow_wechat=allow_wechat,
            force_wechat=force_wechat,
        )
    )
