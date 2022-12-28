import sqlite3


def create_tables(db):
    """
    If not already present, creates all table and indices in the provided sqlite3 db 
    returns True if successfull
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users
            (id INTEGER,
            username TEXT,password TEXT, salt BLOB NOT NULL UNIQUE, PRIMARY KEY(id))
        """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS requisitions
        (id INTEGER NOT NULL UNIQUE, users_id INTEGER NOT NULL, requisition_id TEXT,
        PRIMARY KEY(id), FOREIGN KEY(users_id) REFERENCES users(id));
        """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS categories
        (id INTEGER NOT NULL UNIQUE, category TEXT NOT NULL, PRIMARY KEY(id))
        """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS budget
        (id INTEGER, users_id INTEGER, categories_id INTEGER, amount NUMERIC,
        PRIMARY KEY(id), FOREIGN KEY (categories_id) REFERENCES categories(id),
        FOREIGN KEY(users_id) REFERENCES users(id))å
        """
        )
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_id on users(id)")
    return True
