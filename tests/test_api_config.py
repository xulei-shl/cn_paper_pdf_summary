import os
import unittest
from unittest.mock import patch

import api


class TestApiConfig(unittest.TestCase):
    def test_get_api_bind_host_uses_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(api.get_api_bind_host(), "0.0.0.0")

    def test_get_api_bind_host_reads_env(self):
        with patch.dict(os.environ, {"PDF_SUMMARY_API_BIND_HOST": "127.0.0.1"}, clear=True):
            self.assertEqual(api.get_api_bind_host(), "127.0.0.1")

    def test_get_api_port_uses_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(api.get_api_port(), 8081)

    def test_get_api_port_reads_env(self):
        with patch.dict(os.environ, {"PDF_SUMMARY_API_PORT": "8091"}, clear=True):
            self.assertEqual(api.get_api_port(), 8091)
