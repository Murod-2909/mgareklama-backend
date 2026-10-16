import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase

BASE_DIR = Path(settings.BASE_DIR)

PROBE = """
import json, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'root.settings'
from django.conf import settings
import django
django.setup()
from django.urls import Resolver404, resolve
def routed(path):
    try:
        resolve(path)
        return True
    except Resolver404:
        return False
print(json.dumps({
    'DEBUG': settings.DEBUG,
    'SECRET_KEY': settings.SECRET_KEY,
    'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
    'CORS_ALLOW_ALL_ORIGINS': settings.CORS_ALLOW_ALL_ORIGINS,
    'CORS_ALLOWED_ORIGINS': settings.CORS_ALLOWED_ORIGINS,
    'CSRF_TRUSTED_ORIGINS': settings.CSRF_TRUSTED_ORIGINS,
    'SESSION_COOKIE_SECURE': settings.SESSION_COOKIE_SECURE,
    'CSRF_COOKIE_SECURE': settings.CSRF_COOKIE_SECURE,
    'SECURE_PROXY_SSL_HEADER': settings.SECURE_PROXY_SSL_HEADER,
    'SECURE_CONTENT_TYPE_NOSNIFF': settings.SECURE_CONTENT_TYPE_NOSNIFF,
    'SECURE_SSL_REDIRECT': settings.SECURE_SSL_REDIRECT,
    'media_routed': routed(settings.MEDIA_URL + 'a.txt'),
    'static_routed': routed(settings.STATIC_URL + 'a.txt'),
}))
"""


def load_settings(**env):
    """Import root.settings in a clean process; returns (returncode, settings dict or stderr)."""
    clean = {'PATH': os.environ.get('PATH', ''), 'DJANGO_ENV_FILE': '/nonexistent/.env', **env}
    result = subprocess.run([sys.executable, '-c', PROBE], cwd=BASE_DIR, env=clean, capture_output=True, text=True)
    return result.returncode, (json.loads(result.stdout) if result.returncode == 0 else result.stderr)


class ProductionSettingsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        code, cls.s = load_settings(DJANGO_SECRET_KEY='prod-key', DJANGO_ALLOWED_HOSTS='api.mgareklama.com, www.mgareklama.com')
        assert code == 0, cls.s

    def test_debug_is_off_by_default(self):
        self.assertFalse(self.s['DEBUG'])

    def test_secret_key_comes_from_environment(self):
        self.assertEqual(self.s['SECRET_KEY'], 'prod-key')
        self.assertNotIn('django-insecure', (BASE_DIR / 'root' / 'settings.py').read_text())

    def test_allowed_hosts_are_explicit(self):
        self.assertEqual(self.s['ALLOWED_HOSTS'], ['api.mgareklama.com', 'www.mgareklama.com'])

    def test_cors_is_restricted_to_the_frontend(self):
        self.assertFalse(self.s['CORS_ALLOW_ALL_ORIGINS'])
        self.assertEqual(self.s['CORS_ALLOWED_ORIGINS'], ['https://mgareklama.com', 'https://www.mgareklama.com'])

    def test_csrf_trusted_origins(self):
        self.assertEqual(self.s['CSRF_TRUSTED_ORIGINS'], ['https://api.mgareklama.com', 'https://mgareklama.com'])

    def test_https_hardening(self):
        self.assertTrue(self.s['SESSION_COOKIE_SECURE'])
        self.assertTrue(self.s['CSRF_COOKIE_SECURE'])
        self.assertEqual(self.s['SECURE_PROXY_SSL_HEADER'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertTrue(self.s['SECURE_CONTENT_TYPE_NOSNIFF'])
        self.assertFalse(self.s['SECURE_SSL_REDIRECT'], 'nginx does the redirect')

    def test_media_and_static_are_not_served_by_django(self):
        self.assertFalse(self.s['media_routed'])
        self.assertFalse(self.s['static_routed'])


class DevelopmentSettingsTests(SimpleTestCase):
    def test_debug_values(self):
        for value, expected in (('1', True), ('true', True), ('YES', True), ('0', False), ('false', False), ('', False)):
            with self.subTest(value):
                code, s = load_settings(DJANGO_SECRET_KEY='k', DJANGO_DEBUG=value)
                self.assertEqual((code, s['DEBUG']), (0, expected))

    def test_debug_mode_conveniences(self):
        code, s = load_settings(DJANGO_SECRET_KEY='k', DJANGO_DEBUG='1')
        self.assertEqual(code, 0)
        self.assertIn('http://localhost:3000', s['CORS_ALLOWED_ORIGINS'])
        self.assertEqual(s['ALLOWED_HOSTS'], ['localhost', '127.0.0.1', '[::1]'])
        self.assertTrue(s['media_routed'] and s['static_routed'])
        self.assertFalse(s['SESSION_COOKIE_SECURE'])
        self.assertFalse(s['CORS_ALLOW_ALL_ORIGINS'])

    def test_wildcard_host_is_never_added(self):
        for debug in ('0', '1'):
            code, s = load_settings(DJANGO_SECRET_KEY='k', DJANGO_DEBUG=debug)
            self.assertNotIn('*', s['ALLOWED_HOSTS'])

    def test_production_without_hosts_allows_nothing(self):
        code, s = load_settings(DJANGO_SECRET_KEY='k')
        self.assertEqual(s['ALLOWED_HOSTS'], [])

    def test_extra_cors_origins(self):
        code, s = load_settings(DJANGO_SECRET_KEY='k', DJANGO_CORS_EXTRA_ORIGINS='https://staging.example.com, http://localhost:5173')
        self.assertEqual(s['CORS_ALLOWED_ORIGINS'][-2:], ['https://staging.example.com', 'http://localhost:5173'])


class StartupTests(SimpleTestCase):
    def test_missing_secret_key_stops_startup(self):
        code, error = load_settings()
        self.assertNotEqual(code, 0)
        self.assertIn('DJANGO_SECRET_KEY', error)

    def test_env_file_is_loaded_but_real_environment_wins(self):
        with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False) as f:
            f.write('# comment\nDJANGO_SECRET_KEY="from-file"\nDJANGO_DEBUG=1\nDJANGO_ALLOWED_HOSTS=file.example.com\n')
        try:
            code, s = load_settings(DJANGO_ENV_FILE=f.name)
            self.assertEqual((code, s['SECRET_KEY'], s['DEBUG'], s['ALLOWED_HOSTS']), (0, 'from-file', True, ['file.example.com']))
            code, s = load_settings(DJANGO_ENV_FILE=f.name, DJANGO_DEBUG='0')
            self.assertFalse(s['DEBUG'])
        finally:
            os.unlink(f.name)

    def test_env_example_is_usable_and_dotenv_is_ignored(self):
        example = BASE_DIR / '.env.example'
        code, s = load_settings(DJANGO_ENV_FILE=str(example))
        self.assertEqual((code, s['SECRET_KEY'], s['DEBUG']), (0, 'dev-only', True))
        self.assertIn('.env', (BASE_DIR / '.gitignore').read_text().splitlines())


class CorsBehaviourTests(TestCase):
    def get(self, origin):
        return self.client.get('/api/v1/partners/', HTTP_ORIGIN=origin, HTTP_HOST='testserver')

    def test_only_the_frontend_origins_are_allowed(self):
        for origin in ('https://mgareklama.com', 'https://www.mgareklama.com'):
            self.assertEqual(self.get(origin)['Access-Control-Allow-Origin'], origin)
        for origin in ('https://evil.example', 'https://mgareklama.com.evil.example', 'http://mgareklama.com'):
            self.assertNotIn('Access-Control-Allow-Origin', self.get(origin))
