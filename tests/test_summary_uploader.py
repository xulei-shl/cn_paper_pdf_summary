import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import main
from utils.api_queue import QueueManager
from utils.summary_uploader import load_env, upload_all


class TestSummaryUploader(unittest.IsolatedAsyncioTestCase):
    async def test_upload_all_marks_disabled_lis_rss_as_skipped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            md_path = Path(temp_dir) / "summary.md"
            md_path.write_text("测试摘要内容", encoding="utf-8")

            config = {
                "summary_upload": {
                    "hiagent_rag": {"enabled": False},
                    "lis_rss": {"enabled": False},
                    "memos": {"enabled": False},
                    "blinko": {"enabled": True},
                    "wechat": {"timeout": 30, "max_retries": 2},
                }
            }

            with patch(
                "utils.summary_uploader.upload_to_blinko",
                new=AsyncMock(return_value=True)
            ) as mock_blinko:
                result = await upload_all(
                    md_path=str(md_path),
                    article_id=2931,
                    article_title="测试标题",
                    source_name="单元测试",
                    config=config,
                    skip_lis_rss=False,
                    skip_wechat=True,
                )

        self.assertFalse(result["lis_rss"])
        self.assertTrue(result["blinko"])
        self.assertIn("lis_rss", result["_skipped"])
        self.assertEqual(result["_skip_reasons"]["lis_rss"], "配置禁用")
        mock_blinko.assert_awaited_once()


class TestEnvReload(unittest.TestCase):
    def test_load_env_removes_deleted_key(self):
        env_name = "TELEGRAM_NOTIFY_CHAT_ID"
        old_value = os.environ.get(env_name)

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                env_path = Path(temp_dir) / ".env"
                env_path.write_text(f"{env_name}=123456\n", encoding="utf-8")

                with patch(
                    "utils.summary_uploader._get_env_file_paths",
                    return_value=[env_path],
                ):
                    load_env()
                    self.assertEqual(os.environ.get(env_name), "123456")

                    env_path.write_text("PDF_SUMMARY_PUSH_TELEGRAM_RESULT=true\n", encoding="utf-8")
                    load_env()
                    self.assertNotIn(env_name, os.environ)
        finally:
            if old_value is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = old_value


class TestQueueManagerConfigReload(unittest.TestCase):
    def test_queue_manager_reloads_config_after_file_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                "storage:\n"
                "  download_root: download\n"
                "  logs_root: logs\n"
                "summary_upload:\n"
                "  hiagent_rag:\n"
                "    enabled: true\n",
                encoding="utf-8",
            )

            queue_manager = QueueManager(config_path=str(config_path))
            first_config = queue_manager._ensure_config()
            self.assertTrue(first_config["summary_upload"]["hiagent_rag"]["enabled"])

            config_path.write_text(
                "storage:\n"
                "  download_root: download\n"
                "  logs_root: logs\n"
                "summary_upload:\n"
                "  hiagent_rag:\n"
                "    enabled: false\n",
                encoding="utf-8",
            )

            second_config = queue_manager._ensure_config()
            self.assertFalse(second_config["summary_upload"]["hiagent_rag"]["enabled"])


class TestUploadFailureJudge(unittest.TestCase):
    def test_blinko_success_should_not_be_all_failed(self):
        upload_results = {
            "hiagent_rag": False,
            "lis_rss": False,
            "memos": False,
            "blinko": True,
            "wechat": False,
            "_skipped": ["wechat"],
        }

        self.assertFalse(main._is_all_upload_failed(upload_results))

    def test_all_skipped_should_not_be_all_failed(self):
        upload_results = {
            "hiagent_rag": False,
            "lis_rss": False,
            "memos": False,
            "blinko": False,
            "wechat": False,
            "_skipped": ["hiagent_rag", "lis_rss", "memos", "blinko", "wechat"],
        }

        self.assertFalse(main._is_all_upload_failed(upload_results))
