import sqlite3


class DB:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys = ON')

    def all(self, sql, params=()):
        return self.connection.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.connection.execute(sql, params).fetchone()

    def execute(self, sql, params=()):
        with self.connection:
            self.connection.execute(sql, params)

    def script(self, sql):
        self.connection.executescript(sql)

    def close(self):
        self.connection.close()
