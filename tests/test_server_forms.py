"""Contract: the core rental workflow works through HTML forms without JavaScript."""
import re
import tempfile
import unittest
from pathlib import Path


class ServerFormsTest(unittest.TestCase):
    def setUp(self):
        from app import app, init_db
        self.tmp = tempfile.TemporaryDirectory()
        self.app = app
        app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / 'rental.db'))
        with app.app_context():
            init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_post_and_redirect_without_javascript(self):
        page = self.client.get('/register').text
        token = re.search(r'name="csrf" value="([^"]+)"', page)
        self.assertIsNotNone(token, 'CSRF must be present in server-rendered HTML')
        response = self.client.post('/register', data=dict(csrf=token[1], login='Driver01',
            password='password123', full_name='Иванов Иван', phone='8(999)123-45-67', email='a@example.ru'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login')
        token = re.search(r'name="csrf" value="([^"]+)"', self.client.get('/login').text)[1]
        response = self.client.post('/login', data=dict(csrf=token, login='Driver01', password='password123'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('Мои заявки', self.client.get('/bookings').text)


if __name__ == '__main__':
    unittest.main()
