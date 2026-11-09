import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class EmailSettingsTest(SimpleTestCase):
    def load_settings(self, module, email_env):
        # Fresh imports avoid the test runner's already-loaded settings and local .env.
        script = """
import importlib, json
from unittest.mock import patch
with patch('environ.Env.read_env'):
    settings = importlib.import_module(MODULE)
    names = ('EMAIL_BACKEND', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_USE_TLS', 'EMAIL_USE_SSL')
    print(json.dumps({name: getattr(settings, name, None) for name in names}))
""".replace("MODULE", repr(module))
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("EMAIL_")
        }
        environment.update(email_env)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[3],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_environment_configures_smtp_in_base_development_and_production(self):
        email_env = {
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": "smtp4dev",
            "EMAIL_PORT": "2525",
            "EMAIL_USE_TLS": "True",
            "EMAIL_USE_SSL": "False",
        }
        for module in ("base", "development", "production"):
            with self.subTest(module=module):
                self.assertEqual(
                    self.load_settings(f"config.settings.{module}", email_env),
                    {
                        **email_env,
                        "EMAIL_PORT": 2525,
                        "EMAIL_USE_TLS": True,
                        "EMAIL_USE_SSL": False,
                    },
                )

    def test_development_defaults_to_console_without_backend_override(self):
        settings = self.load_settings("config.settings.development", {})
        self.assertEqual(
            settings["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend"
        )
