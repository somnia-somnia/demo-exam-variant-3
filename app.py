import os,sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config')
from django.core.management import execute_from_command_line as run
if __name__=='__main__':
  if len(sys.argv)==1:
    run(['app.py','migrate','--run-syncdb','--noinput'])
    run(['app.py','runserver','127.0.0.1:'+os.getenv('PORT','5000'),'--noreload'])
  else: run(sys.argv)
