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
key_path = Path(app.instance_path) / 'secret.key'
try:
    with key_path.open('x') as key_file:
        key_file.write(secrets.token_hex(32))
except FileExistsError:
    pass
app.config.update(SECRET_KEY=key_path.read_text(), DATABASE=os.environ.get('RENTAL_DB', str(Path(app.instance_path) / 'rental.db')),
                  MAX_CONTENT_LENGTH=32768, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
CARS = ('LADA Vesta', 'Hyundai Creta', 'Toyota Camry')
CAR_IMAGES = dict(zip(CARS, ('vesta.jpg', 'slide1.jpg', 'fleet.jpg')))
PAYMENTS = ('Наличными', 'Переводом по номеру телефона')
STATUSES = ('Новая', 'Идет аренда', 'Аренда завершена')


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


@app.before_request
def load_user():
    g.user = get_db().one('SELECT * FROM users WHERE id=?', (session.get('user_id'),))
    session.setdefault('csrf', secrets.token_hex(24))
    if request.method == 'POST' and not secrets.compare_digest(session['csrf'].encode(), request.form.get('csrf', '').encode()):
        abort(400, 'Форма устарела. Обновите страницу и повторите действие.')
    if request.endpoint in ('bookings', 'new_booking', 'review', 'admin', 'change_status'):
        if not g.user:
            return redirect(url_for('login'))
        if bool(g.user['is_admin']) != (request.endpoint in ('admin', 'change_status')):
            abort(403, 'Недостаточно прав для этой страницы.')


@app.context_processor
def common():
    return dict(cars=CARS, car_images=CAR_IMAGES, payments=PAYMENTS, statuses=STATUSES)


@app.template_filter('date_ru')
def date_ru(value):
    return datetime.strptime(value, '%Y-%m-%d').strftime('%d.%m.%Y')


@app.route('/')
def index():
    return redirect(url_for('admin' if g.user and g.user['is_admin'] else 'bookings' if g.user else 'login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    errors, values = {}, {}
    if request.method == 'POST':
        values = {key: request.form.get(key, '').strip() for key in ('login', 'full_name', 'phone', 'email')}
        password = request.form.get('password', '')
        rules = dict(login=(r'[A-Za-z0-9]{6,40}', 'Латиница и цифры: от 6 до 40 символов.'),
                     full_name=(r'[А-Яа-яЁё ]{1,150}', 'Введите ФИО кириллицей и пробелами.'),
                     phone=(r'8\([0-9]{3}\)[0-9]{3}-[0-9]{2}-[0-9]{2}', 'Используйте формат 8(XXX)XXX-XX-XX.'),
                     email=(r"(?=.{1,64}@)[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", 'Введите корректный email.'))
        for key, (pattern, message) in rules.items():
            if not re.fullmatch(pattern, values[key]) or len(values[key]) > 254:
                errors[key] = message
        if not 8 <= len(password) <= 128:
            errors['password'] = 'Пароль: от 8 до 128 символов.'
        if get_db().one('SELECT id FROM users WHERE login=?', (values['login'],)):
            errors['login'] = 'Этот логин уже занят.'
        if not errors:
            try:
                get_db().execute('INSERT INTO users(login,password_hash,full_name,phone,email) VALUES(?,?,?,?,?)',
                                 (values['login'], generate_password_hash(password), values['full_name'], values['phone'], values['email']))
            except sqlite3.IntegrityError:
                errors['login'] = 'Этот логин уже занят.'
            else:
                flash('Пользователь создан. Войдите в личный кабинет.')
                return redirect(url_for('login'))
    return render_template('auth.html', title='Регистрация', register=True, errors=errors, values=values), 400 if errors else 200


@app.route('/login', methods=['GET', 'POST'])
def login():
    errors, values = {}, dict(login=request.form.get('login', '').strip())
    if request.method == 'POST':
        user = get_db().one('SELECT * FROM users WHERE login=?', (values['login'],))
        if not user or not check_password_hash(user['password_hash'], request.form.get('password', '')):
            errors['password'] = 'Неверный логин или пароль.'
        else:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('admin' if user['is_admin'] else 'bookings'))
    return render_template('auth.html', title='Вход', register=False, errors=errors, values=values), 400 if errors else 200


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.get('/bookings')
def bookings():
    rows = get_db().all('SELECT b.*, r.text AS review FROM bookings b LEFT JOIN reviews r ON r.booking_id=b.id WHERE b.user_id=? ORDER BY b.id DESC', (g.user['id'],))
    return render_template('bookings.html', title='Мои заявки', rows=rows)


@app.route('/bookings/new', methods=['GET', 'POST'])
def new_booking():
    errors, values = {}, request.form
    if request.method == 'POST':
        if values.get('car') not in CARS:
            errors['car'] = 'Выберите автомобиль из списка.'
        if values.get('payment') not in PAYMENTS:
            errors['payment'] = 'Выберите способ оплаты.'
        try:
            raw = values.get('start_date', '')
            if not re.fullmatch(r'[0-9]{2}\.[0-9]{2}\.[0-9]{4}', raw):
                raise ValueError
            date = datetime.strptime(raw, '%d.%m.%Y').strftime('%Y-%m-%d')
        except ValueError:
            errors['start_date'] = 'Введите существующую дату в формате ДД.ММ.ГГГГ.'
        if not errors:
            get_db().execute('INSERT INTO bookings(user_id,car,start_date,payment) VALUES(?,?,?,?)',
                             (g.user['id'], values['car'], date, values['payment']))
            flash('Заявка отправлена. Администратор рассмотрит её в ближайшее время.')
            return redirect(url_for('bookings'))
    return render_template('new.html', title='Новая заявка', errors=errors, values=values), 400 if errors else 200


@app.post('/bookings/<int(max=9223372036854775807):booking_id>/review')
def review(booking_id):
    row = get_db().one('SELECT * FROM bookings WHERE id=? AND user_id=?', (booking_id, g.user['id']))
    if not row:
        abort(404, 'Заявка не найдена.')
    if row['status'] != STATUSES[2]:
        abort(403, 'Отзыв доступен только после завершения аренды.')
    text = request.form.get('text', '').strip()
    if not 1 <= len(text) <= 2000 or '\0' in text:
        abort(400, 'Отзыв: от 1 до 2000 символов, без нулевых символов.')
    try:
        get_db().execute('INSERT INTO reviews(booking_id,text) VALUES(?,?)', (booking_id, text))
    except sqlite3.IntegrityError:
        abort(409, 'Отзыв для этой заявки уже оставлен.')
    flash('Спасибо! Ваш отзыв сохранён.')
    return redirect(url_for('bookings'))


@app.get('/admin')
def admin():
    status = request.args.get('status', '')
    if status and status not in STATUSES:
        abort(400, 'Неизвестный статус фильтра.')
    rows = get_db().all("SELECT b.*,u.full_name,u.phone,u.email,r.text AS review FROM bookings b JOIN users u ON u.id=b.user_id LEFT JOIN reviews r ON r.booking_id=b.id WHERE (?='' OR b.status=?) ORDER BY b.id DESC", (status, status))
    return render_template('admin.html', title='Панель администратора', rows=rows, selected=status)


@app.post('/admin/<int(max=9223372036854775807):booking_id>/status')
def change_status(booking_id):
    status = request.form.get('status')
    if status not in STATUSES[1:]:
        abort(400, 'Выберите допустимый статус.')
    row = get_db().one('SELECT status FROM bookings WHERE id=?', (booking_id,))
    if not row:
        abort(404, 'Заявка не найдена.')
    if row['status'] == STATUSES[2] and status != STATUSES[2]:
        abort(409, 'Завершённую аренду нельзя возобновить.')
    get_db().execute('UPDATE bookings SET status=? WHERE id=? AND status<>?', (status, booking_id, STATUSES[2]))
    flash('Статус заявки обновлён.')
    return redirect(url_for('admin', status=request.form.get('filter') if request.form.get('filter') in STATUSES else ''))


@app.errorhandler(HTTPException)
def error_page(error):
    return render_template('base.html', title=f'Ошибка {error.code}', message=error.description), error.code, error.get_headers()


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))
