import os
import re
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from db import DB

app = Flask(__name__)
Path(app.instance_path).mkdir(exist_ok=True)
key = Path(app.instance_path) / 'secret.key'
try:
    with key.open('x') as file:
        file.write(secrets.token_hex(32))
except FileExistsError:
    pass
app.config.update(SECRET_KEY=key.read_text(), DATABASE=os.environ.get('RENTAL_DB', str(Path(app.instance_path) / 'rental.db')),
                  MAX_CONTENT_LENGTH=32768, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
CARS = ('LADA Vesta', 'Hyundai Creta', 'Toyota Camry')
PAYMENTS = ('Наличными', 'Переводом по номеру телефона')
STATUSES = ('Новая', 'Идет аренда', 'Аренда завершена')
LOGIN = (('login', 'Логин', 'text'), ('password', 'Пароль', 'password'))
REGISTER = (('login', 'Логин (латиница и цифры, от 6 символов)', 'text'),
            ('password', 'Пароль (от 8 символов)', 'password'), ('full_name', 'ФИО', 'text'),
            ('phone', 'Телефон: 8(999)123-45-67', 'tel'), ('email', 'Email', 'email'))
BOOKING = (('car', 'Автомобиль', CARS), ('start_date', 'Дата начала: ДД.ММ.ГГГГ', 'text'), ('payment', 'Оплата', PAYMENTS))


def get_db():
    if 'db' not in g:
        g.db = DB(app.config['DATABASE'])
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    if 'db' in g:
        g.pop('db').close()


def init_db():
    db = get_db()
    db.script(Path(app.root_path, 'schema.sql').read_text(encoding='utf-8'))
    if not db.one('SELECT id FROM users WHERE login=?', ('Admin',)):
        db.execute('INSERT INTO users(login,password_hash,full_name,phone,email,is_admin) VALUES(?,?,?,?,?,1)',
                   ('Admin', generate_password_hash('StartNET'), 'Администратор', '', ''))


def check(condition, code):
    if not condition:
        abort(code)


def form(title, fields, errors=None):
    return render_template('form.html', title=title, fields=fields, errors=errors or {}), 400 if errors else 200


@app.before_request
def load_user():
    if request.endpoint == 'static':
        return
    g.user = get_db().one('SELECT * FROM users WHERE id=?', (session.get('user_id'),))
    session.setdefault('csrf', secrets.token_hex(24))
    if request.method == 'POST':
        check(secrets.compare_digest(session['csrf'].encode(), request.form.get('csrf', '').encode()), 400)
    if request.path.startswith(('/bookings', '/admin')):
        if not g.user:
            return redirect('/login')
        check(bool(g.user['is_admin']) == request.path.startswith('/admin'), 403)


@app.after_request
def private_response(response):
    if request.endpoint != 'static':
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/')
def index():
    return redirect('/admin' if g.user and g.user['is_admin'] else '/bookings' if g.user else '/login')


@app.route('/register', methods=['GET', 'POST'])
def register():
    errors = {}
    if request.method == 'POST':
        values = {key: request.form.get(key, '').strip() for key in ('login', 'full_name', 'phone', 'email')}
        rules = {'login': r'[A-Za-z0-9]{6,40}', 'full_name': r'[А-Яа-яЁё ]{1,150}',
                 'phone': r'8\([0-9]{3}\)[0-9]{3}-[0-9]{2}-[0-9]{2}',
                 'email': r"(?=.{1,64}@)[A-Za-z0-9!#$%&'*+/=?^_\x60{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_\x60{|}~-]+)*@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"}
        errors = {key: 'Неверный формат.' for key, pattern in rules.items()
                  if not re.fullmatch(pattern, values[key]) or len(values[key]) > 254}
        password = request.form.get('password', '')
        if not 8 <= len(password) <= 128:
            errors['password'] = 'Пароль: 8–128 символов.'
        if not errors:
            try:
                get_db().execute('INSERT INTO users(login,password_hash,full_name,phone,email) VALUES(?,?,?,?,?)',
                                 (values['login'], generate_password_hash(password), values['full_name'], values['phone'], values['email']))
            except sqlite3.IntegrityError:
                errors['login'] = 'Логин занят.'
            else:
                flash('Регистрация завершена. Войдите в аккаунт.')
                return redirect('/login')
    return form('Регистрация', REGISTER, errors)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = get_db().one('SELECT * FROM users WHERE login=?', (request.form.get('login', '').strip(),))
        if not user or not check_password_hash(user['password_hash'], request.form.get('password', '')):
            return form('Вход', LOGIN, {'password': 'Неверный логин или пароль.'})
        session.clear()
        session['user_id'] = user['id']
        return redirect('/admin' if user['is_admin'] else '/bookings')
    return form('Вход', LOGIN)


@app.post('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/bookings/new', methods=['GET', 'POST'])
def new_booking():
    values, errors = request.form, {}
    if request.method == 'POST':
        for key, allowed in [('car', CARS), ('payment', PAYMENTS)]:
            if values.get(key) not in allowed:
                errors[key] = 'Выберите значение из списка.'
        try:
            raw = values.get('start_date', '')
            if not re.fullmatch(r'[0-9]{2}\.[0-9]{2}\.[0-9]{4}', raw):
                raise ValueError
            date = datetime.strptime(raw, '%d.%m.%Y').date().isoformat()
        except ValueError:
            errors['start_date'] = 'Укажите существующую дату: ДД.ММ.ГГГГ.'
        if not errors:
            get_db().execute('INSERT INTO bookings(user_id,car,start_date,payment) VALUES(?,?,?,?)',
                             (g.user['id'], values['car'], date, values['payment']))
            flash('Заявка отправлена.')
            return redirect('/bookings')
    return form('Новая заявка', BOOKING, errors)


@app.get('/bookings')
@app.get('/admin')
def bookings():
    selected = request.args.get('status', '') if g.user['is_admin'] else ''
    check(not selected or selected in STATUSES, 400)
    rows = get_db().all("SELECT b.*,u.full_name,u.phone,u.email,r.text AS review FROM bookings b JOIN users u ON u.id=b.user_id LEFT JOIN reviews r ON r.booking_id=b.id WHERE (? OR b.user_id=?) AND (?='' OR b.status=?) ORDER BY b.id DESC",
                        (g.user['is_admin'], g.user['id'], selected, selected))
    return render_template('bookings.html', title='Панель администратора' if g.user['is_admin'] else 'Мои заявки',
                           rows=rows, statuses=STATUSES, selected=selected)


@app.post('/bookings/<int(max=9223372036854775807):booking_id>/review')
def review(booking_id):
    row = get_db().one('SELECT * FROM bookings WHERE id=? AND user_id=?', (booking_id, g.user['id']))
    check(row, 404)
    check(row['status'] == STATUSES[2], 403)
    text = request.form.get('text', '').strip()
    check(1 <= len(text) <= 2000 and '\0' not in text, 400)
    try:
        get_db().execute('INSERT INTO reviews(booking_id,text) VALUES(?,?)', (booking_id, text))
    except sqlite3.IntegrityError:
        abort(409)
    flash('Отзыв сохранён.')
    return redirect('/bookings')


@app.post('/admin/<int(max=9223372036854775807):booking_id>/status')
def change_status(booking_id):
    status = request.form.get('status')
    check(status in STATUSES[1:], 400)
    row = get_db().one('SELECT status FROM bookings WHERE id=?', (booking_id,))
    check(row, 404)
    check(row['status'] != STATUSES[2] or status == STATUSES[2], 409)
    get_db().execute('UPDATE bookings SET status=? WHERE id=? AND status<>?', (status, booking_id, STATUSES[2]))
    flash('Статус обновлён.')
    selected = request.form.get('filter', '')
    return redirect(url_for('bookings', status=selected) if selected in STATUSES else '/admin')


@app.errorhandler(HTTPException)
def error_page(error):
    message = {400: 'Проверьте данные формы.', 403: 'Действие запрещено.', 404: 'Заявка не найдена.', 409: 'Действие уже выполнено.'}
    headers = dict(error.get_headers())
    headers.pop('Content-Type', None)
    return render_template('form.html', title='Ошибка ' + str(error.code), fields=(),
                           errors={'request': message.get(error.code, error.name)}), error.code, headers


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))
