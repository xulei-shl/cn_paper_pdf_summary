#!/usr/bin/env python3
"""
并行上传模块 - 并行执行五个子系统的MD文件上传

功能：
1. 并行上传MD到HiAgent RAG知识库
2. 并行上传MD内容到LIS-RSS系统更新ai_summary
3. 并行上传MD到Memos
4. 并行上传MD到Blinko
5. 推送摘要到企业微信
6. 汇总各子系统上传结果
"""

import asyncio
import subprocess
import sys
import os
import re
from pathlib import Path
from typing import Dict, Optional
import yaml

# 添加 Blinko 客户端路径
script_dir = Path(__file__).parent.parent
blinko_client_path = script_dir / "summary-update" / "blinko-api" / "src"
if str(blinko_client_path) not in sys.path:
    sys.path.insert(0, str(blinko_client_path))

# 导入企业微信推送模块
try:
    from wechat.client import WeChatClient
    from wechat.message_formatter import MessageFormatter
    WECHAT_AVAILABLE = True
except ImportError:
    WECHAT_AVAILABLE = False


UPLOAD_SUBSYSTEMS = ("hiagent_rag", "lis_rss", "memos", "blinko", "wechat")
UPLOAD_LABELS = {
    "hiagent_rag": "HiAgent RAG",
    "lis_rss": "LIS-RSS",
    "memos": "Memos",
    "blinko": "Blinko",
    "wechat": "WeChat",
}

_MANAGED_ENV_KEYS = set()


def load_config(config_path: str = "config/config.yaml") -> Dict:
    """加载配置文件"""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_env():
    """
    加载并同步 .env 环境变量

    说明：
        长驻进程在运行期间修改 .env 后，调用方期望立即生效。
        这里不只覆盖已有值，也会清理已从 .env 删除的旧键，避免继续沿用过期配置。

    Returns:
        当前从 .env 文件读取到的键值对
    """
    from dotenv import dotenv_values

    global _MANAGED_ENV_KEYS

    env_values: Dict[str, str] = {}
    for env_path in _get_env_file_paths():
        if not env_path.exists():
            continue

        for key, value in dotenv_values(env_path).items():
            if value is not None:
                env_values[key] = value

    removed_keys = _MANAGED_ENV_KEYS - set(env_values.keys())
    for key in removed_keys:
        os.environ.pop(key, None)

    for key, value in env_values.items():
        os.environ[key] = value

    _MANAGED_ENV_KEYS = set(env_values.keys())
    return env_values


def _get_env_file_paths() -> list[Path]:
    """
    获取 .env 文件搜索顺序

    Returns:
        按优先级从低到高排列的 .env 路径列表
    """
    script_env_path = Path(__file__).parent.parent / ".env"
    project_env_path = Path(__file__).parent.parent.parent / ".env"
    return [project_env_path, script_env_path]


def get_env_bool(name: str, default: bool = False) -> bool:
    """读取布尔环境变量，支持常见真值写法"""
    load_env()

    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _is_subsystem_enabled(config: Dict, subsystem: str, default: bool = True) -> bool:
    """
    判断子系统是否在配置中启用

    Args:
        config: 配置字典
        subsystem: 子系统名称
        default: 默认启用状态

    Returns:
        是否启用
    """
    summary_upload = config.get("summary_upload", {})
    subsystem_config = summary_upload.get(subsystem, {})
    return subsystem_config.get("enabled", default)


def _skip_subsystem(
    subsystem: str,
    reason: str,
    skip_reasons: Dict[str, str]
):
    """
    记录跳过原因并返回占位协程

    Args:
        subsystem: 子系统名称
        reason: 跳过原因
        skip_reasons: 跳过原因字典

    Returns:
        占位协程
    """
    print(f"[跳过] {UPLOAD_LABELS[subsystem]}: {reason}")
    skip_reasons[subsystem] = reason
    return asyncio.sleep(0)


def get_upload_status_text(upload_results: Dict[str, object], subsystem: str) -> str:
    """
    获取子系统汇总状态文本

    Args:
        upload_results: 上传结果字典
        subsystem: 子系统名称

    Returns:
        状态文本
    """
    skip_reasons = upload_results.get("_skip_reasons", {})
    if subsystem in skip_reasons:
        return f"⏭️ 跳过（{skip_reasons[subsystem]}）"

    return "✅ 成功" if upload_results.get(subsystem, False) else "❌ 失败"


def print_upload_summary(upload_results: Dict[str, object]) -> None:
    """
    打印上传结果汇总

    Args:
        upload_results: 上传结果字典
    """
    print(f"\n{'='*60}")
    print("  上传结果汇总")
    print(f"{'='*60}")
    print(f"  HiAgent RAG: {get_upload_status_text(upload_results, 'hiagent_rag')}")
    print(f"  LIS-RSS:     {get_upload_status_text(upload_results, 'lis_rss')}")
    print(f"  Memos:       {get_upload_status_text(upload_results, 'memos')}")
    print(f"  Blinko:      {get_upload_status_text(upload_results, 'blinko')}")
    print(f"  WeChat:      {get_upload_status_text(upload_results, 'wechat')}")
    print(f"{'='*60}")


def is_all_executed_uploads_successful(upload_results: Dict[str, object]) -> bool:
    """
    判断所有实际执行的上传任务是否都成功

    Args:
        upload_results: 上传结果字典

    Returns:
        实际执行的任务是否全部成功
    """
    skipped = set(upload_results.get("_skipped", []))

    for subsystem in UPLOAD_SUBSYSTEMS:
        if subsystem in skipped:
            continue
        if not upload_results.get(subsystem, False):
            return False

    return True


async def upload_to_hiagent_rag(md_path: str, config: Dict, delete_md: bool = True) -> bool:
    """
    上传到HiAgent RAG知识库

    Args:
        md_path: MD文件路径
        config: 配置字典
        delete_md: 是否删除MD文件（默认True）

    Returns:
        是否成功
    """
    print(f"\n{'='*60}")
    print(f"  [子系统1/5] HiAgent RAG知识库上传")
    print(f"{'='*60}")

    summary_config = config.get('summary_upload', {}).get('hiagent_rag', {})

    script = summary_config.get('script', 'summary-update/hiagent-rag-upload/upload_knowledge.py')
    script_path = Path(__file__).parent.parent / script

    if not script_path.exists():
        print(f"[错误] HiAgent RAG上传脚本不存在: {script_path}")
        return False

    delete_md = summary_config.get('delete_md', True)

    try:
        print(f"[信息] 脚本路径: {script_path}")
        print(f"[信息] MD文件: {md_path}")
        print(f"[信息] 删除MD: {'是' if delete_md else '否'}")

        cmd = [sys.executable, str(script_path), str(md_path)]
        # upload_knowledge.py 默认行为是不删除文件
        # 要删除文件需要显式传递 --delete true
        # 不删除文件可以什么都不传，或传递 --no-delete
        if delete_md:
            cmd.append("--delete")
            cmd.append("true")
        else:
            cmd.append("--no-delete")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180  # 3分钟超时
        )

        output = result.stdout + result.stderr
        return_code = result.returncode

        print(f"[信息] 返回码: {return_code}")

        if output:
            print(f"[输出] {output[:500]}")
            if len(output) > 500:
                print(f"[输出] ... (总计 {len(output)} 字符)")

        # 检查成功标志
        if re.search(r'成功|success|完成', output, re.IGNORECASE):
            print(f"[成功] HiAgent RAG上传完成")
            return True
        else:
            print(f"[失败] HiAgent RAG上传失败")
            return False

    except subprocess.TimeoutExpired:
        print(f"[错误] HiAgent RAG上传超时")
        return False
    except Exception as e:
        print(f"[错误] HiAgent RAG上传异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def upload_to_lis_rss(article_id: int, md_content: str, config: Dict) -> bool:
    """
    更新LIS-RSS系统的ai_summary

    Args:
        article_id: 文章ID
        md_content: MD文件内容
        config: 配置字典

    Returns:
        是否成功
    """
    print(f"\n{'='*60}")
    print(f"  [子系统2/5] LIS-RSS系统更新")
    print(f"{'='*60}")

    summary_config = config.get('summary_upload', {}).get('lis_rss', {})

    script = summary_config.get('script', 'summary-update/lis-rss-summary-update/update_summary.py')
    script_path = Path(__file__).parent.parent / script

    if not script_path.exists():
        print(f"[错误] LIS-RSS更新脚本不存在: {script_path}")
        return False

    # 读取.env配置
    load_env()

    api_url = os.getenv('LIS_RSS_API_URL')
    username = os.getenv('LIS_RSS_USERNAME')
    password = os.getenv('LIS_RSS_PASSWORD')

    if not api_url or not username or not password:
        print("[错误] LIS-RSS环境变量未配置")
        return False

    try:
        print(f"[信息] 脚本路径: {script_path}")
        print(f"[信息] 文章ID: {article_id}")
        print(f"[信息] API地址: {api_url}")
        print(f"[信息] MD内容长度: {len(md_content)} 字符")

        # 使用stdin传递内容
        result = subprocess.run(
            [sys.executable, str(script_path),
             "--id", str(article_id),
             "--api-url", api_url,
             "--username", username,
             "--password", password,
             "--stdin"],
            input=md_content,
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr
        return_code = result.returncode

        print(f"[信息] 返回码: {return_code}")

        if output:
            print(f"[输出] {output[:500]}")
            if len(output) > 500:
                print(f"[输出] ... (总计 {len(output)} 字符)")

        # 检查成功标志
        if re.search(r'success|成功', output, re.IGNORECASE):
            print(f"[成功] LIS-RSS更新完成")
            return True
        else:
            print(f"[失败] LIS-RSS更新失败")
            return False

    except subprocess.TimeoutExpired:
        print(f"[错误] LIS-RSS更新超时")
        return False
    except Exception as e:
        print(f"[错误] LIS-RSS更新异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def upload_to_memos(title: str, md_content: str, config: Dict) -> bool:
    """
    上传到Memos

    Args:
        title: 文章标题
        md_content: MD文件内容
        config: 配置字典

    Returns:
        是否成功
    """
    print(f"\n{'='*60}")
    print(f"  [子系统3/5] Memos上传")
    print(f"{'='*60}")

    summary_config = config.get('summary_upload', {}).get('memos', {})

    script = summary_config.get('script', 'summary-update/memos/memos_client.py')
    script_path = Path(__file__).parent.parent / script

    if not script_path.exists():
        print(f"[错误] Memos上传脚本不存在: {script_path}")
        return False

    # 读取.env配置
    load_env()

    # 构建内容：标题 + 标签 + 内容
    content = f"#bot #AI速读\n\n**{title}**\n\n---\n\n{md_content}"

    try:
        print(f"[信息] 脚本路径: {script_path}")
        print(f"[信息] 文章标题: {title}")
        print(f"[信息] 内容长度: {len(content)} 字符")

        result = subprocess.run(
            [sys.executable, str(script_path), "create", content],
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr
        return_code = result.returncode

        print(f"[信息] 返回码: {return_code}")

        if output:
            print(f"[输出] {output[:500]}")
            if len(output) > 500:
                print(f"[输出] ... (总计 {len(output)} 字符)")

        # 检查成功标志
        if re.search(r'created|success|成功', output, re.IGNORECASE):
            print(f"[成功] Memos上传完成")
            return True
        else:
            print(f"[失败] Memos上传失败")
            return False

    except subprocess.TimeoutExpired:
        print(f"[错误] Memos上传超时")
        return False
    except Exception as e:
        print(f"[错误] Memos上传异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def upload_to_blinko(title: str, md_content: str, config: Dict) -> bool:
    """
    上传到Blinko

    Args:
        title: 文章标题
        md_content: MD文件内容
        config: 配置字典

    Returns:
        是否成功
    """
    print(f"\n{'='*60}")
    print(f"  [子系统4/5] Blinko上传")
    print(f"{'='*60}")

    # 读取.env配置
    load_env()

    try:
        print(f"[信息] 文章标题: {title}")
        print(f"[信息] 内容长度: {len(md_content)} 字符")

        from blinko_client import BlinkoClient
        client = BlinkoClient()

        content = f"#bot #AI速读\n\n**{title}**\n\n---\n\n{md_content}"

        result = client.notes.upsert(
            content=content,
            note_type=1,
            tags=["bot", "AI速读"]
        )

        note_id = result.get('id')
        print(f"[成功] Blinko上传完成")
        print(f"  笔记ID: {note_id}")
        return True

    except Exception as e:
        print(f"[错误] Blinko上传异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def upload_to_wechat(
    md_content: str,
    article_id: int,
    article_title: str,
    source_name: Optional[str],
    config: Dict
) -> bool:
    """
    推送到企业微信

    Args:
        md_content: MD文件内容
        article_id: 文章ID
        article_title: 文章标题
        source_name: 来源名称
        config: 配置字典

    Returns:
        是否成功
    """
    print(f"\n{'='*60}")
    print(f"  [子系统5/5] 企业微信推送")
    print(f"{'='*60}")

    # 检查模块是否可用
    if not WECHAT_AVAILABLE:
        print("[跳过] 企业微信模块不可用（需要安装 aiohttp）")
        return True

    wechat_config = config.get('summary_upload', {}).get('wechat', {})

    # 读取.env配置
    load_env()

    # 从环境变量获取 webhook key 并组装完整 URL
    webhook_key = os.getenv('WECHAT_WEBHOOK_KEY')
    if not webhook_key:
        print("[错误] 未配置 WECHAT_WEBHOOK_KEY 环境变量")
        return False

    webhook_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={webhook_key}"

    timeout = wechat_config.get('timeout', 30)
    max_retries = wechat_config.get('max_retries', 2)

    try:
        print(f"[信息] Webhook URL: {webhook_url[:50]}...")
        print(f"[信息] 文章ID: {article_id}")
        print(f"[信息] 文章标题: {article_title[:50]}...")

        # 创建客户端
        client = WeChatClient(
            webhook_url=webhook_url,
            timeout=timeout,
            max_retries=max_retries
        )

        # 格式化消息
        formatter = MessageFormatter()
        message = formatter.format_paper_summary(
            title=article_title,
            summary=md_content,
            article_id=article_id,
            source_name=source_name
        )

        print(f"[信息] 消息大小: {len(message.encode('utf-8'))} 字节")

        # 发送消息
        success = await client.send_markdown(message)

        if success:
            print(f"[成功] 企业微信推送完成")
        else:
            print(f"[失败] 企业微信推送失败")

        return success

    except Exception as e:
        print(f"[错误] 企业微信推送异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def upload_all(
    md_path: str,
    article_id: int,
    article_title: str,
    config: Dict,
    source_name: Optional[str] = None,
    skip_lis_rss: bool = False,
    skip_wechat: bool = False
) -> Dict[str, object]:
    """
    并行执行所有上传子系统

    Args:
        md_path: MD文件路径
        article_id: 文章ID
        article_title: 文章标题
        config: 配置字典
        source_name: 来源名称（可选）

    Returns:
        各子系统上传结果字典
    """
    print(f"\n{'='*60}")
    print(f"  并行上传到五个子系统")
    print(f"{'='*60}")
    print(f"[信息] MD文件: {md_path}")
    print(f"[信息] 文章ID: {article_id}")
    print(f"[信息] 文章标题: {article_title}")
    print(f"[信息] 来源: {source_name or '未知'}")

    # 读取MD内容
    md_file = Path(md_path)
    if not md_file.exists():
        print(f"[错误] MD文件不存在: {md_path}")
        return {
            'hiagent_rag': False,
            'lis_rss': False,
            'memos': False,
            'blinko': False,
            'wechat': False,
            '_skipped': [],
            '_skip_reasons': {}
        }

    md_content = md_file.read_text(encoding='utf-8')
    print(f"[信息] MD文件大小: {len(md_content)} 字符")

    summary_config = config.get('summary_upload', {}).get('hiagent_rag', {})
    delete_md = summary_config.get('delete_md', True)

    skip_reasons: Dict[str, str] = {}

    # 创建异步任务。跳过的子系统使用占位协程保持结果索引稳定。
    tasks = []

    if _is_subsystem_enabled(config, "hiagent_rag"):
        tasks.append(upload_to_hiagent_rag(md_path, config, delete_md=delete_md))
    else:
        tasks.append(_skip_subsystem("hiagent_rag", "配置禁用", skip_reasons))

    if skip_lis_rss:
        tasks.append(_skip_subsystem("lis_rss", "未提供文章ID", skip_reasons))
    elif not _is_subsystem_enabled(config, "lis_rss"):
        tasks.append(_skip_subsystem("lis_rss", "配置禁用", skip_reasons))
    else:
        print("[信息] LIS-RSS上传已启用")
        tasks.append(upload_to_lis_rss(article_id, md_content, config))

    if _is_subsystem_enabled(config, "memos"):
        tasks.append(upload_to_memos(article_title, md_content, config))
    else:
        tasks.append(_skip_subsystem("memos", "配置禁用", skip_reasons))

    if _is_subsystem_enabled(config, "blinko"):
        tasks.append(upload_to_blinko(article_title, md_content, config))
    else:
        tasks.append(_skip_subsystem("blinko", "配置禁用", skip_reasons))

    if skip_wechat:
        tasks.append(_skip_subsystem("wechat", "本次流程未启用", skip_reasons))
    elif not WECHAT_AVAILABLE:
        tasks.append(_skip_subsystem("wechat", "依赖不可用", skip_reasons))
    else:
        print("[信息] WeChat推送已启用")
        tasks.append(upload_to_wechat(md_content, article_id, article_title, source_name, config))

    # 并行执行
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 整理结果
    upload_results = {
        'hiagent_rag': results[0] if isinstance(results[0], bool) else False,
        'lis_rss': results[1] if isinstance(results[1], bool) else False,
        'memos': results[2] if isinstance(results[2], bool) else False,
        'blinko': results[3] if isinstance(results[3], bool) else False,
        'wechat': results[4] if isinstance(results[4], bool) else False
    }
    
    # 记录哪些子系统被跳过（用于判断是否"全部失败"）
    upload_results['_skipped'] = list(skip_reasons.keys())
    upload_results['_skip_reasons'] = skip_reasons

    # 处理异常
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[错误] 子系统{i+1}执行异常: {result}")
            import traceback
            traceback.print_exception(type(result), result, result.__traceback__)

    print_upload_summary(upload_results)

    return upload_results


def sync_upload_all(md_path: str, article_id: int, article_title: str, config: Dict) -> Dict[str, object]:
    """
    同步版本的上传（用于非异步环境）
    
    Args:
        md_path: MD文件路径
        article_id: 文章ID
        article_title: 文章标题
        config: 配置字典
        
    Returns:
        各子系统上传结果字典
    """
    return asyncio.run(upload_all(md_path, article_id, article_title, config))


# 测试入口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        md_path = sys.argv[1]
    else:
        md_path = "test.md"
    
    # 测试
    try:
        config = load_config()
        print(f"[OK] 配置加载成功")
        
        # 测试上传
        print(f"\n[测试] 上传文件: {md_path}")
        
    except Exception as e:
        print(f"[ERROR] {e}")
