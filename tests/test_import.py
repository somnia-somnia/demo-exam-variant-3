"""One-time migration preserves an old SQLite file and existing password hashes."""
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from werkzeug.security import generate_password_hash,check_password_hash
from tests.mysql_support import Database

ROOT=Path(__file__).resolve().parents[1]

class LegacyImportTest(unittest.TestCase):
    def test_readonly_import_preserves_ids_data_and_hashes(self):
        target=Database()
        try:
            with tempfile.TemporaryDirectory() as directory:
                source=Path(directory)/'old.db'
                hashed=generate_password_hash('Existing123')
                with sqlite3.connect(source) as db:
                    db.executescript('''CREATE TABLE users (note TEXT DEFAULT '',id INTEGER PRIMARY KEY,
                      login TEXT,password_hash TEXT,full_name TEXT,phone TEXT,email TEXT,is_admin INTEGER);
                      CREATE TABLE bookings (id INTEGER PRIMARY KEY,user_id INTEGER,car TEXT,
                      start_date TEXT,payment TEXT,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                      CREATE TABLE reviews (id INTEGER PRIMARY KEY,booking_id INTEGER,text TEXT);''')
                    db.execute('INSERT INTO users(id,login,password_hash,full_name,phone,email,is_admin) VALUES(?,?,?,?,?,?,?)',
                        (7,'OldUser1',hashed,'Иван Иванов','8(999)123-45-67','old@example.ru',0))
                    db.execute('INSERT INTO bookings(id,user_id,car,start_date,payment,status) VALUES(?,?,?,?,?,?)',
                        (9,7,'Toyota Camry','2026-12-02','Наличными','Аренда завершена'))
                    db.execute('INSERT INTO reviews VALUES(?,?,?)',(11,9,'Прежний отзыв'))
                db.close()
                before=hashlib.sha256(source.read_bytes()).hexdigest()
                result=subprocess.run([sys.executable,'tools/import_legacy.py',str(source)],cwd=ROOT,
                    env=dict(os.environ,MYSQL_DATABASE=target.name),capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
                with target.connection.cursor() as cursor:
                    cursor.execute('SELECT id,password_hash,login_key FROM users WHERE login=%s',('OldUser1',))
                    row=cursor.fetchone()
                    self.assertEqual(row,(7,hashed,hashlib.sha256(b'olduser1').hexdigest()))
                    self.assertTrue(check_password_hash(row[1],'Existing123'))
                    cursor.execute('SELECT user_id,status FROM bookings WHERE id=9')
                    self.assertEqual(cursor.fetchone(),(7,'Аренда завершена'))
                    cursor.execute('SELECT booking_id,text FROM reviews WHERE id=11')
                    self.assertEqual(cursor.fetchone(),(9,'Прежний отзыв'))
                again=subprocess.run([sys.executable,'tools/import_legacy.py',str(source)],cwd=ROOT,
                    env=dict(os.environ,MYSQL_DATABASE=target.name),capture_output=True,text=True,encoding='utf-8')
                self.assertNotEqual(again.returncode,0,'Must refuse an occupied target')
        finally:
            target.close()
