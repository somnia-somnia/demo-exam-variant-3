import re
from urllib.parse import parse_qs, urlsplit
from datetime import date
from types import SimpleNamespace
from django.test import TransactionTestCase
from django.db import connection, IntegrityError, transaction
from rental.models import Booking
from tests.client import Browser
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import patch
from django.db import connections
from rental.models import Review


class RentalTest(TransactionTestCase):
    reset_sequences = True
    def test_server_pages_with_no_javascript_dependency(self):
        for path in ['/login', '/register']:
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn('{%', page.text)
            self.assertNotIn('{{', page.text)
            self.assertIn('<form', page.text)
            self.assertRegex(page.text, r'name="csrfmiddlewaretoken" value="[A-Za-z0-9]{64}"')
            self.assertEqual(page.headers['Cache-Control'], 'no-store')
            page.close()

    def setUp(self):
        self.app = SimpleNamespace(test_client=Browser)
        self.client = Browser()
        self.user = dict(login='Driver01', password='password123', full_name='Иванов Иван Иванович',
                         phone='8(999)123-45-67', email='ivan@example.ru')

    def post(self, url, data=None, client=None):
        client = client or self.client
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', client.get('/login').text)[1]
        return client.post(url, data={**(data or {}), 'csrfmiddlewaretoken': token})

    def register(self, **changes):
        return self.post('/register', self.user | changes)

    def login(self, login='Driver01', password='password123', client=None):
        return self.post('/login', dict(login=login, password=password), client)

    def query(self, sql, params=()):
        with connection.cursor() as cursor:
            cursor.execute(sql.replace('?', '%s'), params)
            return list(cursor.fetchall())

    def booking(self, **changes):
        return self.post('/bookings/new', dict(car='LADA Vesta', start_date='02.12.2026',
                                              payment='Наличными') | changes)

    def ready(self):
        self.register()
        self.login()
        self.booking()

    def test_registration_stores_hash_and_unique_login(self):
        self.assertEqual(self.register().status_code, 302)
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
                self.assertIn('aria-invalid="true"', response.text)
        self.assertEqual(len(self.query('SELECT id FROM users')), 1)

    def test_registration_accepts_boundaries_and_yo(self):
        self.assertEqual(self.register(login='User12', password='12345678', full_name='Фёдор Ёлкин').status_code, 302)

    def test_registration_has_no_unlisted_upper_limits(self):
        self.assertEqual(self.register(login='Driver' * 12, password='p' * 160,
                                       full_name='Иван ' * 40).status_code, 302)

    def test_public_landing_lists_all_three_models(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        for car in ('LADA Vesta', 'Hyundai Creta', 'Toyota Camry'):
            self.assertIn(car, page.text)
        self.assertIn('/bookings/new', page.text)

    def test_admin_login_has_no_registration_length_hint(self):
        self.assertNotIn('от 6', self.client.get('/login').text)

    def test_insert_works_with_extra_user_column(self):
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE users ADD COLUMN note VARCHAR(20) DEFAULT '' FIRST")
        self.assertEqual(self.register().status_code, 302)
        self.assertEqual(self.login().status_code, 302)

    def test_completed_rental_can_be_reopened(self):
        self.ready()
        admin = self.app.test_client()
        self.login('Admin', 'StartNET', admin)
        self.post('/admin/1/status', dict(status='Аренда завершена'), admin)
        response = self.post('/admin/1/status', dict(status='Идет аренда'), admin)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.query('SELECT status FROM bookings')[0][0], 'Идет аренда')
        self.assertEqual(self.post('/bookings/1/review', dict(text='Рано')).status_code, 403)

    def test_status_change_waits_for_finished_review_transaction(self):
        self.ready()
        admin = Browser()
        self.login('Admin', 'StartNET', admin)
        self.post('/admin/1/status', dict(status='Аренда завершена'), admin)
        entered, release = Event(), Event()
        create = Review.objects.create

        def paused_create(**values):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('Review transaction not released')
            return create(**values)

        def threaded_post(client, path, values):
            try:
                return self.post(path, values, client).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            with patch('rental.views.Review.objects.create', side_effect=paused_create):
                review = pool.submit(threaded_post, self.client, '/bookings/1/review', dict(text='Завершено'))
                try:
                    self.assertTrue(entered.wait(5))
                    status = pool.submit(threaded_post, admin, '/admin/1/status', dict(status='Идет аренда'))
                    with self.assertRaises(TimeoutError):
                        status.result(timeout=.4)
                finally:
                    release.set()
                self.assertEqual(review.result(timeout=5), 302)
                self.assertEqual(status.result(timeout=5), 302)
        self.assertEqual(self.query('SELECT status FROM bookings')[0][0], 'Идет аренда')
        self.assertEqual(self.query('SELECT COUNT(*) FROM reviews')[0][0], 1)

    def test_reviews_have_no_unlisted_count_or_length_limit(self):
        self.ready()
        admin = self.app.test_client()
        self.login('Admin', 'StartNET', admin)
        self.post('/admin/1/status', dict(status='Аренда завершена'), admin)
        self.assertEqual(self.post('/bookings/1/review', dict(text='Отзыв ' * 500)).status_code, 302)
        self.assertEqual(self.post('/bookings/1/review', dict(text='Второй отзыв')).status_code, 302)
        page = self.client.get('/bookings').text
        self.assertEqual(page.count('id="booking-1"'), 1)
        self.assertIn('Второй отзыв', page)
        self.assertIn('/bookings/1/review', page)

    def test_email_rejects_invalid_parts_and_accepts_subdomains(self):
        for i, email in enumerate(['<a>@x.ru', 'a@<x>.ru', 'a@x,com.ru', 'a@-x.ru', 'a@x_.ru',
                                   '.a@example.ru', 'a..b@example.ru', 'a.@example.ru', 'a@example.ru\0',
                                   'a' * 65 + '@example.ru', 'a@' + 'x' * 64 + '.ru']):
            with self.subTest(email=email):
                self.assertEqual(self.register(login=f'BadMail{i:02}', email=email).status_code, 400)
        self.assertEqual(self.register(login='ValidMail1', email='ivan_petrov+rent@sub.example.ru').status_code, 302)
        for i, email in enumerate(["o'connor@example.ru", 'a!b@example.ru']):
            self.assertEqual(self.register(login=f'MailSpecial{i}', email=email).status_code, 302)
        self.assertEqual(len(self.query('SELECT id FROM users')), 4)

    def test_login_failures_and_admin_routing(self):
        self.register()
        for login, password in [('Driver01', 'wrong'), ("' OR 1=1 --", 'password123'), ('', '')]:
            self.assertEqual(self.login(login, password).status_code, 400)
        self.assertEqual(self.login().location, '/bookings')
        self.assertEqual(self.login('Admin', 'StartNET').location, '/admin')

    def test_login_required_and_logout(self):
        for url in ['/bookings', '/bookings/new', '/admin']:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.register()
        self.login()
        self.assertEqual(self.post('/logout').status_code, 302)
        self.assertEqual(self.client.get('/bookings').status_code, 302)

    def test_booking_validates_and_defaults(self):
        self.register()
        self.login()
        for changes in [dict(car='BMW'), dict(start_date='31.02.2026'), dict(start_date='2026-12-02'),
                        dict(start_date='2.12.2026'), dict(payment='Картой'), dict(car='')]:
            self.assertEqual(self.booking(**changes).status_code, 400)
        self.assertEqual(self.booking().status_code, 302)
        self.assertEqual(self.query('SELECT car, start_date, status FROM bookings')[0],
                         ('LADA Vesta', date(2026, 12, 2), 'Новая'))
        self.assertIn('02.12.2026', self.client.get('/bookings').text)

    def test_owner_isolation_and_no_role_escalation(self):
        self.ready()
        self.post('/logout')
        self.register(login='Other01', full_name='Петров Пётр', is_admin='1')
        self.login('Other01')
        self.assertNotIn('<article', self.client.get('/bookings').text)
        self.assertEqual(self.client.get('/admin').status_code, 403)
        self.assertEqual(self.post('/admin/1/status', dict(status='Аренда завершена')).status_code, 403)
        self.assertEqual(self.post('/bookings/1/review', dict(text='Чужой отзыв')).status_code, 404)
        self.booking(user_id='2', status='Аренда завершена')
        owner = self.query('SELECT id FROM users WHERE login=?', ('Other01',))[0][0]
        self.assertEqual(self.query('SELECT user_id, status FROM bookings WHERE id=2')[0], (owner, 'Новая'))

    def test_admin_filter_status_and_review_lifecycle(self):
        self.ready()
        self.assertEqual(self.post('/bookings/1/review', dict(text='Рано')).status_code, 403)
        admin = self.app.test_client()
        self.login('Admin', 'StartNET', admin)
        self.assertIn('Иванов', admin.get('/admin').text)
        self.assertEqual(self.post('/admin/1/status', dict(status='???'), admin).status_code, 400)
        response = self.post('/admin/1/status', dict(status='Идет аренда', filter='Идет аренда'), admin)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.location).path, '/admin')
        self.assertEqual(parse_qs(urlsplit(response.location).query), {'status': ['Идет аренда']})
        self.assertNotIn('<article', admin.get('/admin?status=Новая').text)
        self.assertIn('LADA Vesta', admin.get('/admin?status=Идет аренда').text)
        self.assertEqual(self.post('/admin/1/status', dict(status='Аренда завершена'), admin).status_code, 302)
        self.assertEqual(self.post('/bookings/1/review', dict(text='   ')).status_code, 400)
        self.assertEqual(self.post('/bookings/1/review', dict(text='<script>alert(1)</script>')).status_code, 302)
        html = self.client.get('/bookings').text
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertEqual(self.post('/bookings/1/review', dict(text='Ещё')).status_code, 302)
        self.assertEqual(self.post('/admin/1/status', dict(status='Идет аренда'), admin).status_code, 302)
        self.assertEqual(self.post('/admin/999/status', dict(status='Идет аренда'), admin).status_code, 404)

    def test_csrf_rejects_missing_and_wrong_tokens(self):
        self.client.get('/login')
        self.assertEqual(self.client.post('/register', data=self.user).status_code, 403)
        self.assertEqual(self.client.post('/register', data=self.user | {'csrfmiddlewaretoken': 'bad'}).status_code, 403)
        self.assertEqual(len(self.query('SELECT id FROM users')), 1)

    def test_malformed_unicode_csrf_returns_form_error(self):
        self.client.get('/login')
        self.assertEqual(self.client.post('/register', data=self.user | {'csrfmiddlewaretoken': 'подделка'}).status_code, 403)

    def test_foreign_keys_enabled_in_application_connection(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(user_id=999, car='LADA Vesta', start_date='2026-12-02', payment='Наличными')

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

    def test_html_never_exposes_hashes_or_other_owners(self):
        self.ready()
        page = self.client.get('/bookings?is_admin=1&user_id=999').text
        self.assertNotIn('password', page)
        self.assertIn('LADA Vesta', page)
        self.post('/logout')
        self.assertEqual(self.client.get('/bookings?is_admin=1').status_code, 302)
        self.register(login='Other01')
        self.login('Other01')
        with self.client.session_transaction() as session:
            session['is_admin'] = 1
        self.assertNotIn('<article', self.client.get('/bookings?is_admin=1&user_id=2').text)
        self.assertEqual(self.client.get('/admin').status_code, 403)

    def test_html_errors_and_http_methods(self):
        response = self.register(login='abc')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.is_json)
        self.assertIn('aria-invalid="true"', response.text)
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 405)
        self.assertIn('POST', response.headers['Allow'])
        self.login('Admin', 'StartNET')
        self.assertEqual(self.client.get('/admin?status=invalid').status_code, 400)
