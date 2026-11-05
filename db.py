import sqlite3


class DB:
  def __init__(self,path):
    self.c=sqlite3.connect(path)
    self.c.row_factory=sqlite3.Row
    self.c.execute('PRAGMA foreign_keys=ON')

  def query(self,sql,params=(),many=False):
    with self.c:
      cursor=self.c.execute(sql,params)
      return cursor.fetchall() if many else cursor.fetchone()

  def close(self):
    self.c.close()
