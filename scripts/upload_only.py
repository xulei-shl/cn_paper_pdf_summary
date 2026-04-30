#!/usr/bin/env python3
"""
独立上传脚本 - 只执行步骤4的异步上传

功能：
1. 从指定目录找到MD文件
2. 只执行步骤4的异步上传到五个子系统
"""

import sys
import asyncio
import argparse
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入工具模块
from utils.summary_uploader import (
    UPLOAD_SUBSYSTEMS,
    is_all_executed_uploads_successful,
    print_upload_summary,
    upload_all,
    load_config
)


def find_md_file(directory: str) -> Optional[Path]:
    """
    在指定目录中查找MD文件

    Args:
        directory: 目录路径

    Returns:
        第一个找到的MD文件路径，如果没有则返回None
    """
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        print(f"[错误] 目录不存在或不是目录: {directory}")
        return None

    md_files = list(dir_path.glob("*.md"))
    if not md_files:
        print(f"[错误] 在目录中未找到MD文件: {directory}")
        return None

    if len(md_files) > 1:
        print(f"[警告] 在目录中找到多个MD文件，将使用第一个: {md_files[0]}")

    return md_files[0]


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description='独立上传脚本 - 只执行步骤4的异步上传')
    parser.add_argument('--directory', required=True, help='包含MD文件的目录路径')
    parser.add_argument('--article-id', type=int, help='文章ID（可选，用于LIS-RSS更新）')
    parser.add_argument('--article-title', help='文章标题（可选）')
    parser.add_argument('--source-name', help='来源名称（可选）')
    parser.add_argument('--skip-lis-rss', action='store_true', help='跳过LIS-RSS上传')
    parser.add_argument('--skip-wechat', action='store_true', help='跳过企业微信推送')
    args = parser.parse_args()

    print_section("独立上传脚本启动")

    # 查找MD文件
    print(f"[信息] 查找MD文件: {args.directory}")
    md_path = find_md_file(args.directory)

    if not md_path:
        print("[失败] 未找到MD文件，退出")
        sys.exit(1)

    print(f"[成功] 找到MD文件: {md_path}")

    # 如果没有提供文章标题，使用MD文件名（去掉.md扩展名）
    article_title = args.article_title
    if not article_title:
        article_title = md_path.stem

    print(f"[信息] 文章标题: {article_title}")

    # 如果没有提供文章ID，跳过LIS-RSS上传
    article_id = args.article_id
    skip_lis_rss = args.skip_lis_rss
    if article_id is None:
        print("[信息] 未提供文章ID，将跳过LIS-RSS上传")
        skip_lis_rss = True
        article_id = 0
    else:
        print(f"[信息] 文章ID: {article_id}")

    # 加载配置
    print_section("加载配置")
    try:
        config = load_config()
        print(f"[成功] 配置加载成功")
    except Exception as e:
        print(f"[失败] 配置加载失败: {e}")
        sys.exit(1)

    # 执行上传
    print_section("执行步骤4: 异步上传")

    try:
        upload_results = asyncio.run(upload_all(
            md_path=str(md_path),
            article_id=article_id,
            article_title=article_title,
            source_name=args.source_name,
            config=config,
            skip_lis_rss=skip_lis_rss,
            skip_wechat=args.skip_wechat
        ))

        print_section("上传结果汇总")
        print_upload_summary(upload_results)

        skipped = set(upload_results.get('_skipped', []))
        executed_count = len(UPLOAD_SUBSYSTEMS) - len(skipped)
        all_success = is_all_executed_uploads_successful(upload_results)

        if all_success and executed_count == 0:
            print("\n[完成] 没有需要执行的上传任务，所有子系统均已跳过")
            sys.exit(0)
        if all_success and skipped:
            print("\n[完成] 实际执行的上传任务全部成功，部分子系统已跳过")
            sys.exit(0)
        if all_success:
            print("\n[成功] 所有上传任务完成")
            sys.exit(0)
        else:
            print("\n[部分失败] 部分上传任务失败")
            sys.exit(1)

    except Exception as e:
        print(f"\n[错误] 上传过程异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户取消执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
