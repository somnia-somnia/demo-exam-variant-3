"""Contract: the core rental workflow works through HTML forms without JavaScript."""
import re
from django.test import TransactionTestCase
from tests.client import Browser


class ServerFormsTest(TransactionTestCase):
    def setUp(self):
        self.client = Browser()

    def test_html_post_and_redirect_without_javascript(self):
        page = self.client.get('/register').text
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
        self.assertIsNotNone(token, 'CSRF must be present in server-rendered HTML')
        response = self.client.post('/register', data=dict(csrfmiddlewaretoken=token[1], login='Driver01',
            password='password123', full_name='Иванов Иван', phone='8(999)123-45-67', email='a@example.ru'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', self.client.get('/login').text)[1]
        response = self.client.post('/login', data=dict(csrfmiddlewaretoken=token, login='Driver01', password='password123'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('Мои заявки', self.client.get('/bookings').text)
