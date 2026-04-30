import unittest
from unittest.mock import AsyncMock, patch

from utils.notifier import (
    build_error_message,
    dispatch_success_notifications,
    split_telegram_message,
)


class TestNotifierHelpers(unittest.TestCase):
    def test_split_telegram_message_preserves_long_text(self):
        text = ("第一行\n" * 1000).strip()
        chunks = split_telegram_message(text, max_length=100)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunk.replace("\n", "") for chunk in chunks), text.replace("\n", ""))

    def test_build_error_message_contains_stage_summary(self):
        message = build_error_message(
            title="测试标题",
            reason="PDF下载失败",
            article_id=12,
            source_name="测试来源",
            stages={
                "pdf_download": "failed",
                "pdf_validate": "skipped",
                "pdf_summary": "skipped",
                "upload": {"memos": False, "blinko": True},
            },
        )

        self.assertIn("测试标题", message)
        self.assertIn("PDF下载失败", message)
        self.assertIn("文章ID: 12", message)
        self.assertIn("Memos: ❌", message)
        self.assertIn("Blinko: ✅", message)


class TestNotifierDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_success_notifications_by_config(self):
        config = {
            "summary_upload": {
                "wechat": {
                    "timeout": 30,
                }
            }
        }

        with patch("utils.notifier.get_env_bool") as mock_get_env_bool, \
             patch("utils.notifier.send_telegram_message", return_value=True) as mock_send, \
             patch("utils.notifier.upload_to_wechat", new_callable=AsyncMock, return_value=True) as mock_wechat:
            mock_get_env_bool.side_effect = lambda name, default=False: {
                "PDF_SUMMARY_PUSH_TELEGRAM_LOG": True,
                "PDF_SUMMARY_PUSH_TELEGRAM_RESULT": False,
                "PDF_SUMMARY_PUSH_WECHAT": True,
            }.get(name, default)

            result = await dispatch_success_notifications(
                title="测试标题",
                article_id=0,
                source_name="API调用",
                md_content="这是摘要正文",
                stages={"pdf_download": "success", "pdf_summary": "success", "upload": {}},
                config=config,
            )

        self.assertEqual(result["telegram_log"], True)
        self.assertEqual(result["telegram_result"], False)
        self.assertEqual(result["wechat"], True)
        self.assertEqual(mock_send.call_count, 1)
        mock_wechat.assert_awaited_once()

    async def test_dispatch_success_notifications_skip_telegram_log_for_telegram_source(self):
        config = {
            "summary_upload": {
                "wechat": {
                    "timeout": 30,
                }
            }
        }

        with patch("utils.notifier.get_env_bool") as mock_get_env_bool, \
             patch("utils.notifier.send_telegram_message", return_value=True) as mock_send, \
             patch("utils.notifier.upload_to_wechat", new_callable=AsyncMock, return_value=False):
            mock_get_env_bool.side_effect = lambda name, default=False: {
                "PDF_SUMMARY_PUSH_TELEGRAM_LOG": True,
                "PDF_SUMMARY_PUSH_TELEGRAM_RESULT": True,
                "PDF_SUMMARY_PUSH_WECHAT": False,
            }.get(name, default)

            result = await dispatch_success_notifications(
                title="测试标题",
                article_id=0,
                source_name="Telegram命令",
                md_content="这是摘要正文",
                stages={"pdf_download": "success", "pdf_summary": "success", "upload": {}},
                config=config,
                allow_telegram_log=False,
            )

        self.assertEqual(result["telegram_log"], False)
        self.assertEqual(result["telegram_result"], True)
        self.assertEqual(result["wechat"], False)
        self.assertEqual(mock_send.call_count, 1)
