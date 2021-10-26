import sqlite3


def create_tables(connection):
  c = connection.cursor()  
  """
  If not already present, creates all table and indices in the provided sqlite3 connection 
  returns True if successfull
  """
  c.execute("""
  CREATE TABLE IF NOT EXISTS users
  (id INTEGER, enduser_id BLOB NOT NULL UNIQUE, reference BLOB NOT NULL UNIQUE, 
  username TEXT,password TEXT, requsition_id TEXT, PRIMARY KEY(id))
  """)
  c.execute("""CREATE TABLE IF NOT EXISTS categories
  (id INTEGER, category TEXT, PRIMARY KEY(id))
  """)
  c.execute("""CREATE TABLE IF NOT EXISTS budget
  (id INTEGER, users_id INTEGER, categories_id INTEGER, amount NUMERIC,
  PRIMARY KEY(id), FOREIGN KEY (categories_id) REFERENCES categories(id),
  FOREIGN KEY(users_id) REFERENCES users(id))  
  """)
  c.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_id on users(id)")
  c.execute("CREATE UNIQUE INDEX IF NOT EXISTS categories_id on categories(id)")
  return True


