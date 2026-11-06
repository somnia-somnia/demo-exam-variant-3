from django.db import IntegrityError,transaction
from django.core.exceptions import BadRequest,PermissionDenied
from django.http import Http404,HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.middleware.csrf import rotate_token
from django.urls import path
from django.views.static import serve
from django.conf import settings
from django.views.decorators.http import require_POST,require_http_methods
from werkzeug.security import check_password_hash,generate_password_hash
from .models import User,Booking,Review,CARS,ST,key
from .forms import Login,Register,Rent
PAGES={'/register':('Регистрация',Register,'Зарегистрироваться'),
 '/login':('Вход',Login,'Войти'),'/bookings/new':('Новая заявка',Rent,'Отправить')}
def check(ok,code):
  if not ok: raise {400:BadRequest,403:PermissionDenied,404:Http404}[code]
def access(next):
  def call(r):
    if r.path.startswith('/static/'): return next(r)
    r.u=User.objects.filter(pk=r.session.get('user_id')).first()
    if r.path.startswith(('/bookings','/admin')):
      if not r.u: return redirect('/login')
      if r.u.is_admin!=r.path.startswith('/admin'): return HttpResponse(status=403)
    response=next(r)
    response['Cache-Control']='no-store'
    return response
  return call
def home(r): return render(r,'home.html',dict(u=r.u,cars=CARS,title='Аренда авто',slides=range(1,5)))
@require_http_methods(['GET','POST'])
def forms(r):
  u=r.u
  title,kind,button=PAGES[r.path]
  form=kind(r.POST if r.method=='POST' else None)
  if form.is_valid():
    v=form.cleaned_data
    if r.path=='/login':
      user=User.objects.filter(login_key=key(v['login'])).first()
      if user and check_password_hash(user.password_hash,v['password']):
        r.session.flush()
        r.session['user_id']=user.pk
        rotate_token(r)
        return redirect('/admin' if user.is_admin else '/bookings')
      form.add_error('password','Неверный логин или пароль.')
    elif r.path=='/register':
      try:
        v['password_hash']=generate_password_hash(v.pop('password'))
        with transaction.atomic(): User.objects.create(**v)
        return redirect('/login')
      except IntegrityError: form.add_error('login','Логин занят.')
    else:
      Booking.objects.create(user=r.u,**v)
      return redirect('/bookings')
  return render(r,'form.html',locals(),status=400 if r.method=='POST' else 200)
@require_POST
def logout(r):
  r.session.flush()
  return redirect('/login')
def bookings(r):
  u,s=r.u,ST
  filt=r.GET.get('status','') if r.u.is_admin else ''
  check(not filt or filt in ST,400)
  rows=Booking.objects.order_by('-id')
  if not r.u.is_admin: rows=rows.filter(user=r.u)
  if filt: rows=rows.filter(status=filt)
  title='Панель администратора' if r.u.is_admin else 'Мои заявки'
  return render(r,'bookings.html',locals())
@require_POST
@transaction.atomic
def update(r,bid):
  b=get_object_or_404(Booking.objects.select_for_update(),pk=bid)
  check(r.u.is_admin or b.user_id==r.u.pk,404)
  if r.u.is_admin:
    status=r.POST.get('status')
    check(status in ST[1:],400)
    b.status=status
    b.save(update_fields=['status'])
    filt=r.POST.get('filter','')
    return redirect('/admin?status='+filt if filt in ST else '/admin')
  check(b.status==ST[2],403)
  text=r.POST.get('text','').strip()
  check(bool(text) and '\0' not in text,400)
  Review.objects.create(booking=b,text=text)
  return redirect('/bookings')
urlpatterns=[path('',home),path('logout',logout),path('bookings',bookings),path('admin',bookings),
 path('bookings/<int:bid>/review',update),path('admin/<int:bid>/status',update),
 path('static/<path:path>',serve,{'document_root':settings.BASE/'static'})]
urlpatterns += [path(p[1:],forms) for p in PAGES]
