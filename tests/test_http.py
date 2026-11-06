"""End-to-end HTTP audit against isolated Django and real MySQL processes."""
import http.cookiejar
import html
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path
from tests.mysql_support import Database

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class Session:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, data=None):
        encoded = None if data is None else urllib.parse.urlencode(data).encode()
        try:
            response = self.opener.open(self.base + urllib.parse.quote(path, safe='/?=&'), encoded, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read().decode('utf-8')

    def post(self, path, data=None, token=True):
        fields = dict(data or {})
        if token:
            fields['csrfmiddlewaretoken'] = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', self.request('/login')[2])[1]
        return self.request(path, fields)


class HTTPAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = Database()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.base = f'http://127.0.0.1:{sock.getsockname()[1]}'
        cls.server = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT,
            env=dict(os.environ, MYSQL_DATABASE=cls.database.name, PORT=cls.base.rsplit(':', 1)[1]),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.steps, cls.passed = [], False
        for _ in range(100):
            try:
                Session(cls.base).request('/login')
                break
            except OSError:
                time.sleep(.1)
        else:
            cls.server.terminate()
            raise RuntimeError('Isolated HTTP server did not start')

    @classmethod
    def tearDownClass(cls):
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(cls.server.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.database.close()
        (ROOT / 'docs/http-results.json').write_text(json.dumps(dict(
            result='PASS' if cls.passed else 'FAIL', transport='real HTTP, four independent cookie jars',
            checks=cls.steps), ensure_ascii=False, indent=2), encoding='utf-8')

    def expect(self, label, response, status):
        self.steps.append(dict(check=label, expected=status, actual=response[0]))
        self.assertEqual(response[0], status, label)
        return response

    def test_real_http_workflow_and_access(self):
        guest, alice, bob, admin = (Session(self.base) for _ in range(4))
        user = dict(login='Driver01', password='Test1234', full_name='Первый Пользователь',
                    phone='8(999)123-45-67', email='driver1@example.ru')
        for path in ['/bookings', '/bookings/new', '/admin']:
            self.expect('guest GET ' + path, guest.request(path), 302)
        response = self.expect('csrf missing', guest.post('/register', user, token=False), 403)
        for field in user:
            self.expect('required ' + field, guest.post('/register', user | {field: ''}), 400)
        for field, value in [('login', 'abc12'), ('login', 'Логин12'), ('password', '1234567'),
                             ('full_name', 'John Smith'), ('phone', '+79991234567'), ('email', '<a>@x.ru')]:
            self.expect('invalid ' + field, guest.post('/register', user | {field: value}), 400)
        self.expect('register Alice', alice.post('/register', user | {'is_admin': '1'}), 302)
        self.expect('duplicate case-insensitive login', guest.post('/register', user | {'login': 'driver01'}), 400)
        self.expect('register Bob', bob.post('/register', user | dict(login='Driver02', full_name='Второй Пользователь')), 302)
        self.expect('wrong password', alice.post('/login', dict(login='Driver01', password='wrong')), 400)
        self.expect('SQL injection login', alice.post('/login', dict(login="' OR 1=1 --", password='Test1234')), 400)
        for client, login, password in [(alice, 'Driver01', 'Test1234'), (bob, 'Driver02', 'Test1234'), (admin, 'Admin', 'StartNET')]:
            response = self.expect('login ' + login, client.post('/login', dict(login=login, password=password)), 302)
            self.assertIn('HttpOnly', response[1].get('Set-Cookie', ''))
            self.assertIn('SameSite=Lax', response[1].get('Set-Cookie', ''))
        booking = dict(car='LADA Vesta', start_date='01.12.2026', payment='Наличными')
        self.expect('guest POST booking', guest.post('/bookings/new', booking), 302)
        self.expect('all booking fields required', alice.post('/bookings/new'), 400)
        for change in [dict(car='BMW'), dict(start_date='31.02.2026'), dict(start_date='2026-12-01'), dict(payment='Картой')]:
            self.expect('invalid booking', alice.post('/bookings/new', booking | change), 400)
        for car in ['LADA Vesta', 'Hyundai Creta', 'Toyota Camry']:
            payment = 'Наличными' if car == 'LADA Vesta' else 'Переводом по номеру телефона'
            self.expect('Alice books ' + car, alice.post('/bookings/new', booking | dict(car=car, payment=payment, user_id='3', status='Аренда завершена')), 302)
        self.expect('Bob books', bob.post('/bookings/new', booking | dict(car='Toyota Camry')), 302)
        ids = lambda response: {int(value) for value in re.findall(r'id="booking-(\d+)"', response[2])}
        self.assertEqual(ids(alice.request('/bookings')), {1, 2, 3})
        self.assertEqual(ids(bob.request('/bookings')), {4})
        self.assertEqual(ids(admin.request('/admin')), {1, 2, 3, 4})
        self.steps.append(dict(check='owner isolation and admin all four bookings', actual='PASS'))
        for client in [alice, bob]:
            self.expect('regular admin page forbidden', client.request('/admin'), 403)
            self.expect('regular status forbidden', client.post('/admin/1/status', dict(status='Аренда завершена')), 403)
        for path in ['/bookings', '/bookings/new']:
            self.expect('admin regular page forbidden', admin.request(path), 403)
        self.expect('admin user review forbidden', admin.post('/bookings/1/review', dict(text='Admin')), 403)
        self.expect('guest review forbidden', guest.post('/bookings/1/review', dict(text='Guest')), 302)
        self.expect('guest admin status forbidden', guest.post('/admin/1/status', dict(status='Идет аренда')), 302)
        self.expect('new review forbidden', alice.post('/bookings/1/review', dict(text='Early')), 403)
        self.expect('start rent', admin.post('/admin/1/status', dict(status='Идет аренда')), 302)
        self.expect('active review forbidden', alice.post('/bookings/1/review', dict(text='Early')), 403)
        self.expect('foreign review forbidden', bob.post('/bookings/1/review', dict(text='Foreign')), 404)
        self.expect('finish rent', admin.post('/admin/1/status', dict(status='Аренда завершена')), 302)
        self.expect('foreign finished review forbidden', bob.post('/bookings/1/review', dict(text='Foreign')), 404)
        self.expect('empty review rejected', alice.post('/bookings/1/review', dict(text='   ')), 400)
        self.expect('NUL review rejected', alice.post('/bookings/1/review', dict(text='\0test')), 400)
        review = 'Уникальный отзыв <script>alert(1)</script>'
        self.expect('owner finished review saved', alice.post('/bookings/1/review', dict(text=review)), 302)
        self.expect('second review permitted', alice.post('/bookings/1/review', dict(text='Again')), 302)
        for client, path in [(alice, '/bookings'), (admin, '/admin')]:
            page = client.request(path)[2]
            self.assertIn(html.escape(review), page)
            self.assertNotIn('<script>alert(1)</script>', page)
            self.assertNotIn('password_hash', page)
        self.assertNotIn('Уникальный отзыв', bob.request('/bookings')[2])
        for status, wanted in [('Новая', {2, 3, 4}), ('Идет аренда', set()), ('Аренда завершена', {1})]:
            self.assertEqual(ids(admin.request('/admin?status=' + status)), wanted)
        self.expect('unknown filter rejected', admin.request('/admin?status=bad'), 400)
        self.expect('unknown status rejected', admin.post('/admin/2/status', dict(status='bad')), 400)
        self.expect('finished rental can reopen', admin.post('/admin/1/status', dict(status='Идет аренда')), 302)
        self.expect('review forbidden after reopening', alice.post('/bookings/1/review', dict(text='Early')), 403)
        self.expect('oversized review ID', alice.post('/bookings/9223372036854775808/review', dict(text='Text')), 404)
        self.expect('oversized status ID', admin.post('/admin/9223372036854775808/status', dict(status='Идет аренда')), 404)
        response = self.expect('GET logout is read-only', alice.request('/logout'), 405)
        self.assertIn('POST', response[1]['Allow'])
        self.expect('logout', alice.post('/logout'), 302)
        self.expect('logged-out history blocked', alice.request('/bookings'), 302)
        with self.database.connection.cursor() as cursor:
            cursor.execute('CHECK TABLE users,bookings,reviews')
            self.assertTrue(all(row[-1] == 'OK' for row in cursor.fetchall()))
            cursor.execute('SELECT user_id,status FROM bookings WHERE id=1')
            owner, status = cursor.fetchone()
            cursor.execute('SELECT id,is_admin,password_hash FROM users WHERE login=%s', ('Driver01',))
            user_id, is_admin, hashed = cursor.fetchone()
            self.assertEqual((owner,status), (user_id,'Идет аренда'))
            self.assertEqual(is_admin, 0)
            self.assertNotEqual(hashed, 'Test1234')
            cursor.execute('SELECT COUNT(*) FROM reviews')
            self.assertEqual(cursor.fetchone()[0], 2)
        self.steps.append(dict(check='MySQL CHECK TABLE, hashes, stored ownership/role, two reviews', actual='PASS'))
        type(self).passed = True


if __name__ == '__main__':
    unittest.main()
