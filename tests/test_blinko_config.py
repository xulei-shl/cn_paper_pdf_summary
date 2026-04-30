import os
import sys
import tempfile
import unittest
from pathlib import Path


BLINKO_SRC_PATH = Path(__file__).resolve().parents[1] / "summary-update" / "blinko-api" / "src"
if str(BLINKO_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(BLINKO_SRC_PATH))

from blinko_client.base import get_project_env_path, load_config  # noqa: E402


class TestBlinkoConfig(unittest.TestCase):
    def test_default_project_env_path_points_to_repo_root(self):
        expected = Path(__file__).resolve().parents[1] / ".env"
        self.assertEqual(get_project_env_path(), expected)

    def test_load_config_supports_explicit_env_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "BLINKO_BASE_URL=http://example.com\nBLINKO_API_KEY=test-key\n",
                encoding="utf-8"
            )

            old_base_url = os.environ.get("BLINKO_BASE_URL")
            old_api_key = os.environ.get("BLINKO_API_KEY")
            os.environ.pop("BLINKO_BASE_URL", None)
            os.environ.pop("BLINKO_API_KEY", None)

            try:
                config = load_config(env_path)
            finally:
                if old_base_url is None:
                    os.environ.pop("BLINKO_BASE_URL", None)
                else:
                    os.environ["BLINKO_BASE_URL"] = old_base_url

                if old_api_key is None:
                    os.environ.pop("BLINKO_API_KEY", None)
                else:
                    os.environ["BLINKO_API_KEY"] = old_api_key

            self.assertEqual(config.base_url, "http://example.com")
            self.assertEqual(config.api_key, "test-key")
