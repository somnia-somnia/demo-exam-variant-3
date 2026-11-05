import os,re,secrets,sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask,abort,g,redirect,render_template as render,request as req,session
from werkzeug.security import check_password_hash,generate_password_hash
from db import DB

app=Flask(__name__)
Path(app.instance_path).mkdir(exist_ok=True)
app.config.update(SECRET_KEY=secrets.token_hex(32),MAX_CONTENT_LENGTH=32768,SESSION_COOKIE_SAMESITE='Lax',
         DATABASE=os.getenv('RENTAL_DB',app.instance_path+'/rental.db'))
CARS=('LADA Vesta','Hyundai Creta','Toyota Camry')
PAYMENTS=('Наличными','Переводом по номеру телефона')
STATUSES=('Новая','Идет аренда','Аренда завершена')
ACCOUNT=[
  ('login','Логин: латиница/цифры, от 6','text',r'[A-Za-z0-9]{6,40}'),
  ('password','Пароль: 8–128','password',r'[\s\S]{8,128}'),
  ('full_name','ФИО','text',r'[А-Яа-яЁё ]{1,150}'),
  ('phone','Телефон: 8(999)123-45-67','tel',r'8\([0-9]{3}\)[0-9]{3}-[0-9]{2}-[0-9]{2}'),
  ('email','Email','email',r"(?ai)(?=.{1,64}@)[\w!#$%&'*+/=?^_\x60{|}~-]+(?:\.[\w!#$%&'*+/=?^_\x60{|}~-]+)*@(?:[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?\.)+[a-z]{2,63}")]
RENT=[('car','Автомобиль',CARS,''),
  ('start_date','Дата: ДД.ММ.ГГГГ','text',r'[0-9]{2}\.[0-9]{2}\.[0-9]{4}'),
  ('payment','Оплата',PAYMENTS,'')]
PAGES={
  '/register': ('Регистрация',ACCOUNT,'Зарегистрироваться'),
  '/login': ('Вход',ACCOUNT[:2],'Войти'),
  '/bookings/new': ('Новая заявка',RENT,'Отправить')}

def get_db():
  if 'db' not in g:
    g.db=DB(app.config['DATABASE'])
  return g.db

@app.teardown_appcontext
def close_db(error=None):
  if 'db' in g:
    g.pop('db').close()

def init_db():
  db=get_db()
  db.c.executescript(Path(app.root_path,'schema.sql').read_text(encoding='utf-8'))
  db.query('INSERT OR IGNORE INTO users VALUES(NULL,?,?,?,?,?,1)',
         ('Admin',generate_password_hash('StartNET'),'Администратор','',''))

def check(ok,code):
  if not ok: abort(code)

@app.before_request
def access():
  if req.endpoint=='static':
    return
  g.u=get_db().query('SELECT * FROM users WHERE id=?',(session.get('user_id'),))
  session.setdefault('csrf',secrets.token_hex(24))
  if req.method=='POST':
    check(secrets.compare_digest(session['csrf'].encode(),req.form.get('csrf','').encode()),400)
  if req.path.startswith(('/bookings','/admin')):
    if not g.u:
      return redirect('/login')
    check(bool(g.u['is_admin'])==req.path.startswith('/admin'),403)

@app.after_request
def private(resp):
  resp.headers['Cache-Control']='no-store'
  return resp

@app.context_processor
def common():
  return dict(u=g.u,s=STATUSES)

@app.get('/')
def index():
  return redirect('/login' if not g.u else '/admin' if g.u['is_admin'] else '/bookings')

def forms():
  title,fields,button=PAGES[req.path]
  v={n: req.form.get(n,'') for n,*_ in fields}
  v={n: val if n=='password' else val.strip() for n,val in v.items()}
  db,errors=get_db(),{}
  if req.method=='POST':
    if req.path=='/login':
      user=db.query('SELECT * FROM users WHERE login=?',(v['login'],))
      if user and check_password_hash(user['password_hash'],v['password']):
        session.clear()
        session['user_id']=user['id']
        return redirect('/admin' if user['is_admin'] else '/bookings')
      errors['password']='Неверный логин или пароль.'
    else:
      for n,label,kind,rule in fields:
        if len(v[n])>254 or not (re.fullmatch(rule,v[n]) if isinstance(kind,str) else v[n] in kind):
          errors[n]='Неверный формат.'
      if 'start_date' in v:
        try:
          date=datetime.strptime(v['start_date'],'%d.%m.%Y').date().isoformat()
        except ValueError:
          errors['start_date']='Неверный формат.'
      if not errors:
        if req.path=='/register':
          try:
            db.query('INSERT INTO users VALUES(NULL,?,?,?,?,?,0)',
                 (v['login'],generate_password_hash(v['password']),v['full_name'],v['phone'],v['email']))
            return redirect('/login')
          except sqlite3.IntegrityError:
            errors['login']='Логин занят.'
        else:
          db.query('INSERT INTO bookings(user_id,car,start_date,payment) VALUES(?,?,?,?)',
               (g.u['id'],v['car'],date,v['payment']))
          return redirect('/bookings')
  return render('form.html',**locals()),400 if errors else 200

@app.post('/logout')
def logout():
  session.clear()
  return redirect('/login')

@app.get('/bookings')
@app.get('/admin')
def bookings():
  filt=req.args.get('status','') if g.u['is_admin'] else ''
  check(not filt or filt in STATUSES,400)
  rows=get_db().query("SELECT b.*,full_name,phone,email,text review FROM bookings b JOIN users u ON u.id=user_id LEFT JOIN reviews r ON booking_id=b.id WHERE (? OR user_id=?) AND (?='' OR status=?) ORDER BY b.id DESC",
             (g.u['is_admin'],g.u['id'],filt,filt),True)
  title='Панель администратора' if g.u['is_admin'] else 'Мои заявки'
  return render('bookings.html',**locals())

@app.post('/bookings/<int(max=9223372036854775807):bid>/review')
@app.post('/admin/<int(max=9223372036854775807):bid>/status')
def update(bid):
  db=get_db()
  admin=g.u['is_admin']
  row=db.query('SELECT * FROM bookings WHERE id=? AND (? OR user_id=?)',(bid,admin,g.u['id']))
  check(row,404)
  if admin:
    status=req.form.get('status')
    check(status in STATUSES[1:],400)
    check(row['status']!=STATUSES[2] or status==STATUSES[2],409)
    db.query('UPDATE bookings SET status=? WHERE id=? AND status<>?',(status,bid,STATUSES[2]))
    filt=req.form.get('filter','')
    return redirect('/admin?status='+filt if filt in STATUSES else '/admin')
  check(row['status']==STATUSES[2],403)
  text=req.form.get('text','').strip()
  check(1<=len(text)<=2000 and '\0' not in text,400)
  try:
    db.query('INSERT INTO reviews(booking_id,text) VALUES(?,?)',(bid,text))
  except sqlite3.IntegrityError:
    abort(409)
  return redirect('/bookings')

for path in PAGES:
  app.add_url_rule(path,view_func=forms,methods=['GET','POST'])
with app.app_context():
  init_db()
if __name__=='__main__':
  app.run(port=int(os.getenv('PORT',5000)))
