from datetime import datetime
from django import forms as F
from .models import CARS,PAYMENTS
R=F.RegexField
class Login(F.Form):
  login=F.CharField(label='Логин')
  password=F.CharField(label='Пароль',widget=F.PasswordInput,strip=False)
class Register(Login):
  login=R(r'\A[A-Za-z0-9]{6,}\Z',label='Логин: латиница/цифры ≥6',strip=True)
  password=F.CharField(min_length=8,label='Пароль: от 8',widget=F.PasswordInput,strip=False)
  full_name=R(r'\A[А-Яа-яЁё ]+\Z',label='ФИО',strip=True)
  phone=R(r'\A8\([0-9]{3}\)[0-9]{3}-[0-9]{2}-[0-9]{2}\Z',label='Телефон: 8(999)123-45-67',strip=True)
  email=R(r"(?ai)\A(?=.{1,64}@)[\w!#$%&'*+/=?^_\x60{|}~-]+(?:\.[\w!#$%&'*+/=?^_\x60{|}~-]+)*@(?:[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?\.)+[a-z]{2,63}\Z",label='Email',strip=True)
class Rent(F.Form):
  car=F.ChoiceField(choices=[('','Выберите')]+[(x,x) for x in CARS],label='Автомобиль')
  start_date=R(r'\A[0-9]{2}\.[0-9]{2}\.[0-9]{4}\Z',label='Дата: ДД.ММ.ГГГГ',strip=True)
  payment=F.ChoiceField(choices=[('','Выберите')]+[(x,x) for x in PAYMENTS],label='Оплата')
  def clean_start_date(self):
    try: return datetime.strptime(self.cleaned_data['start_date'],'%d.%m.%Y').date()
    except ValueError: raise F.ValidationError('Неверная дата.')
