"""Disposable real MySQL databases for development integration tests."""
import os
import uuid
import MySQLdb


class Database:
    def __init__(self):
        self.name = 'rental_test_' + uuid.uuid4().hex
        self.connection = MySQLdb.connect(host=os.getenv('MYSQL_HOST', '127.0.0.1'),
            port=int(os.getenv('MYSQL_PORT', '3306')), user=os.getenv('MYSQL_USER', 'root'),
            passwd=os.getenv('MYSQL_PASSWORD', ''), charset='utf8mb4')
        with self.connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{self.name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
        self.connection.select_db(self.name)

    def close(self):
        with self.connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{self.name}`')
        self.connection.close()
