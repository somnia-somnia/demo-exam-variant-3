from hashlib import sha256
from django.db import models as M
from django.db.models.signals import post_migrate
from werkzeug.security import generate_password_hash
CARS={'LADA Vesta':'vesta.jpg','Hyundai Creta':'slide1.jpg','Toyota Camry':'camry.webp'}
PAYMENTS=('Наличными','Переводом по номеру телефона')
ST=('Новая','Идет аренда','Аренда завершена')
def key(login): return sha256(login.lower().encode()).hexdigest()
class User(M.Model):
  login,password_hash,full_name,phone,email=[M.TextField() for _ in range(5)]
  login_key=M.CharField(max_length=64,unique=True)
  is_admin=M.BooleanField(default=False)
  def save(self,*args,**kw):
    self.login_key=key(self.login)
    super().save(*args,**kw)
  class Meta: db_table='users'
class Booking(M.Model):
  user=M.ForeignKey(User,on_delete=M.PROTECT)
  car,payment=[M.TextField() for _ in range(2)]
  start_date=M.DateField()
  status=M.TextField(default=ST[0])
  class Meta: db_table='bookings'
class Review(M.Model):
  booking=M.ForeignKey(Booking,on_delete=M.PROTECT)
  text=M.TextField()
  class Meta: db_table='reviews'
def seed(sender,**kw):
  User.objects.get_or_create(login_key=key('Admin'),defaults=dict(login='Admin',
    password_hash=generate_password_hash('StartNET'),is_admin=True))
post_migrate.connect(seed)
