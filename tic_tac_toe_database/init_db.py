import sqlite3

def initialize_database(db_file='tic_tac_toe.db', schema_file='schema.sql'):
    """Initializes the tic tac toe SQLite database from schema.sql."""
    with open(schema_file, 'r') as f:
        schema = f.read()
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Database initialized: {db_file}")

if __name__ == '__main__':
    initialize_database()
