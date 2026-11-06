"""One-time import; the source SQLite database is opened read-only."""
import os,sys,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config')
import django
django.setup()
from django.core.management import call_command
from django.db import transaction
from rental.models import User,Booking,Review
call_command('migrate',run_syncdb=True,interactive=False,verbosity=0)
if Booking.objects.exists() or User.objects.filter(is_admin=False).exists():
  raise ValueError('Целевая БД должна быть пустой.')
source=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
source.row_factory=sqlite3.Row
with transaction.atomic():
  for model in (User,Booking,Review):
    names=[f.attname for f in model._meta.local_fields if f.name!='login_key']
    for row in source.execute('SELECT '+','.join(names)+' FROM '+model._meta.db_table):
      values=dict(row)
      model.objects.update_or_create(pk=values.pop('id'),defaults=values)
source.close()
print('Данные импортированы. Исходная БД сохранена.')
