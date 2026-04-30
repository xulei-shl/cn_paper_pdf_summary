import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import main
from utils.summary_uploader import upload_all


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
