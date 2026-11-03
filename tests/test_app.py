import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class RentalTest(unittest.TestCase):
    def test_plain_pages_and_state_api(self):
        state = self.client.get('/api')
        self.assertEqual(state.status_code, 200)
        self.assertTrue(state.is_json)
        self.assertEqual(state.json['rows'], [])
        self.assertIsNone(state.json['user'])
        self.assertEqual(len(state.json['csrf']), 48)
        self.assertEqual(state.headers['Cache-Control'], 'no-store')
        for path in ['/login', '/register']:
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn('{%', page.text)
            self.assertNotIn('{{', page.text)
            self.assertIn('<form', page.text)
            page.close()

    def setUp(self):
        from app import app, init_db
        self.tmp = tempfile.TemporaryDirectory()
        self.app = app
        app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / 'test.db'))
        with app.app_context():
            init_db()
        self.client = app.test_client()
        self.user = dict(login='Driver01', password='password123', full_name='Иванов Иван Иванович',
                         phone='8(999)123-45-67', email='ivan@example.ru')

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, url, data=None, client=None):
        client = client or self.client
        token = client.get('/api').json['csrf']
        return client.post(url, data={**(data or {}), 'csrf': token})

    def register(self, **changes):
        return self.post('/register', self.user | changes)

    def login(self, login='Driver01', password='password123', client=None):
        return self.post('/login', dict(login=login, password=password), client)

    def query(self, sql, params=()):
        with closing(sqlite3.connect(self.app.config['DATABASE'])) as con:
            return con.execute(sql, params).fetchall()

    def booking(self, **changes):
        return self.post('/bookings/new', dict(car='LADA Vesta', start_date='02.12.2026',
                                              payment='Наличными') | changes)

    def ready(self):
        self.register()
        self.login()
        self.booking()

    def test_registration_stores_hash_and_unique_login(self):
        self.assertEqual(self.register().status_code, 200)
        stored = self.query('SELECT password_hash, is_admin FROM users WHERE login=?', ('Driver01',))[0]
        self.assertNotEqual(stored[0], self.user['password'])
        self.assertEqual(stored[1], 0)
        self.assertEqual(self.register(login='driver01').status_code, 400)
        self.assertEqual(len(self.query('SELECT id FROM users')), 2)

    def test_each_registration_rule_and_required_field(self):
        for field in self.user:
            with self.subTest(empty=field):
                self.assertEqual(self.register(**{field: ''}).status_code, 400)
        for field, value in [('login', 'abc12'), ('login', 'драйвер1'), ('login', "abc' OR 1=1"),
                             ('password', '1234567'), ('full_name', 'John Smith'),
                             ('full_name', '   '), ('phone', '+79991234567'),
                             ('email', 'bad@'), ('email', 'a b@example.ru')]:
            with self.subTest(field=field, value=value):
                response = self.register(**{field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json['errors'])
        self.assertEqual(len(self.query('SELECT id FROM users')), 1)

    def test_registration_accepts_boundaries_and_yo(self):
        self.assertEqual(self.register(login='User12', password='12345678', full_name='Фёдор Ёлкин').status_code, 200)

    def test_email_rejects_invalid_parts_and_accepts_subdomains(self):
        for i, email in enumerate(['<a>@x.ru', 'a@<x>.ru', 'a@x,com.ru', 'a@-x.ru', 'a@x_.ru',
                                   '.a@example.ru', 'a..b@example.ru', 'a.@example.ru', 'a@example.ru\0',
                                   'a' * 65 + '@example.ru', 'a@' + 'x' * 64 + '.ru']):
            with self.subTest(email=email):
                self.assertEqual(self.register(login=f'BadMail{i:02}', email=email).status_code, 400)
        self.assertEqual(self.register(login='ValidMail1', email='ivan_petrov+rent@sub.example.ru').status_code, 200)
        for i, email in enumerate(["o'connor@example.ru", 'a!b@example.ru']):
            self.assertEqual(self.register(login=f'MailSpecial{i}', email=email).status_code, 200)
        self.assertEqual(len(self.query('SELECT id FROM users')), 4)

    def test_login_failures_and_admin_routing(self):
        self.register()
        for login, password in [('Driver01', 'wrong'), ("' OR 1=1 --", 'password123'), ('', '')]:
            self.assertEqual(self.login(login, password).status_code, 400)
        self.assertEqual(self.login().json['next'], '/bookings')
        self.assertEqual(self.login('Admin', 'StartNET').json['next'], '/admin')

    def test_login_required_and_logout(self):
        for url in ['/bookings', '/bookings/new', '/admin']:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.register()
        self.login()
        self.assertEqual(self.post('/logout').status_code, 200)
        self.assertEqual(self.client.get('/bookings').status_code, 302)

    def test_booking_validates_and_defaults(self):
        self.register()
        self.login()
        for changes in [dict(car='BMW'), dict(start_date='31.02.2026'), dict(start_date='2026-12-02'),
                        dict(start_date='2.12.2026'), dict(payment='Картой'), dict(car='')]:
            self.assertEqual(self.booking(**changes).status_code, 400)
        self.assertEqual(self.booking().status_code, 200)
        self.assertEqual(self.query('SELECT car, start_date, status FROM bookings')[0],
                         ('LADA Vesta', '2026-12-02', 'Новая'))
        self.assertEqual(self.client.get('/api').json['rows'][0]['start_date'], '2026-12-02')

    def test_owner_isolation_and_no_role_escalation(self):
        self.ready()
        self.post('/logout')
        self.register(login='Other01', full_name='Петров Пётр', is_admin='1')
        self.login('Other01')
        self.assertEqual(self.client.get('/api').json['rows'], [])
        self.assertEqual(self.client.get('/admin').status_code, 403)
        self.assertEqual(self.post('/admin/1/status', dict(status='Аренда завершена')).status_code, 403)
        self.assertEqual(self.post('/bookings/1/review', dict(text='Чужой отзыв')).status_code, 404)
        self.booking(user_id='2', status='Аренда завершена')
        self.assertEqual(self.query('SELECT user_id, status FROM bookings WHERE id=2')[0], (3, 'Новая'))

    def test_admin_filter_status_and_review_lifecycle(self):
        self.ready()
        self.assertEqual(self.post('/bookings/1/review', dict(text='Рано')).status_code, 403)
        admin = self.app.test_client()
        self.login('Admin', 'StartNET', admin)
        self.assertIn('Иванов', admin.get('/api').json['rows'][0]['full_name'])
        self.assertEqual(self.post('/admin/1/status', dict(status='???'), admin).status_code, 400)
        self.assertEqual(self.post('/admin/1/status', dict(status='Идет аренда'), admin).status_code, 200)
        self.assertEqual(admin.get('/api?status=Новая').json['rows'], [])
        self.assertEqual(admin.get('/api?status=Идет аренда').json['rows'][0]['car'], 'LADA Vesta')
        self.assertEqual(self.post('/admin/1/status', dict(status='Аренда завершена'), admin).status_code, 200)
        self.assertEqual(self.post('/bookings/1/review', dict(text='   ')).status_code, 400)
        self.assertEqual(self.post('/bookings/1/review', dict(text='<script>alert(1)</script>')).status_code, 200)
        self.assertEqual(self.client.get('/api').json['rows'][0]['review'], '<script>alert(1)</script>')
        self.assertEqual(self.post('/bookings/1/review', dict(text='Ещё')).status_code, 409)
        self.assertEqual(self.post('/admin/1/status', dict(status='Идет аренда'), admin).status_code, 409)
        self.assertEqual(self.post('/admin/999/status', dict(status='Идет аренда'), admin).status_code, 404)

    def test_csrf_rejects_missing_and_wrong_tokens(self):
        self.client.get('/api')
        self.assertEqual(self.client.post('/register', data=self.user).status_code, 400)
        self.assertEqual(self.client.post('/register', data=self.user | {'csrf': 'bad'}).status_code, 400)
        self.assertEqual(len(self.query('SELECT id FROM users')), 1)

    def test_malformed_unicode_csrf_returns_form_error(self):
        self.client.get('/api')
        self.assertEqual(self.client.post('/register', data=self.user | {'csrf': 'подделка'}).status_code, 400)

    def test_foreign_keys_enabled_in_application_connection(self):
        from app import get_db
        with self.app.app_context():
            with self.assertRaises(sqlite3.IntegrityError):
                get_db().execute('INSERT INTO bookings(user_id, car, start_date, payment) VALUES(?,?,?,?)',
                                 (999, 'LADA Vesta', '2026-12-02', 'Наличными'))

    def test_oversized_booking_ids_return_not_found(self):
        self.ready()
        for value in [str(2**63), '9' * 500, '9' * 5000]:
            self.assertEqual(self.post(f'/bookings/{value}/review', dict(text='Текст')).status_code, 404)
        self.login('Admin', 'StartNET')
        for value in [str(2**63), '9' * 500, '9' * 5000]:
            self.assertEqual(self.post(f'/admin/{value}/status', dict(status='Идет аренда')).status_code, 404)

    def test_nul_review_is_validation_error_not_duplicate(self):
        self.ready()
        admin = self.app.test_client()
        self.login('Admin', 'StartNET', admin)
        self.post('/admin/1/status', dict(status='Аренда завершена'), admin)
        self.assertEqual(self.post('/bookings/1/review', dict(text='\0test')).status_code, 400)
        self.assertEqual(self.query('SELECT id FROM reviews'), [])

    def test_api_never_exposes_hashes_or_other_owners(self):
        self.ready()
        api = self.client.get('/api?is_admin=1&user_id=999').json
        self.assertEqual(set(api['user']), {'id', 'full_name', 'is_admin'})
        self.assertNotIn('password', str(api))
        self.assertEqual({r['user_id'] for r in api['rows']}, {2})
        self.post('/logout')
        self.assertEqual(self.client.get('/api?is_admin=1').json['rows'], [])
        self.register(login='Other01')
        self.login('Other01')
        with self.client.session_transaction() as session:
            session['is_admin'] = 1
        self.assertEqual(self.client.get('/api?is_admin=1&user_id=2').json['rows'], [])
        self.assertEqual(self.client.get('/admin').status_code, 403)

    def test_json_errors_and_http_methods(self):
        response = self.register(login='abc')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.is_json)
        self.assertIn('login', response.json['errors'])
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 405)
        self.assertIn('POST', response.headers['Allow'])
        self.login('Admin', 'StartNET')
        self.assertEqual(self.client.get('/api?status=invalid').status_code, 400)


if __name__ == '__main__':
    unittest.main()
