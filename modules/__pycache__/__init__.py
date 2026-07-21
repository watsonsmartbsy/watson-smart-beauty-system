import sqlite3

conn = sqlite3.connect('database.db')

# -------------------------
# USERS TABLE
# -------------------------
conn.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    password TEXT,
    role TEXT
)
''')


# -------------------------
# ANALYSIS HISTORY TABLE
# -------------------------
conn.execute('''
CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    image_path TEXT,
    brightness REAL,
    redness REAL,
    condition TEXT,
    product TEXT,
    advice TEXT
)
''')


# -------------------------
# PRODUCTS TABLE
# -------------------------
conn.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    category TEXT,
    skin_type TEXT,
    price REAL
)
''')


# -------------------------
# RULE ENGINE TABLE
# -------------------------
conn.execute('''
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_name TEXT,
    min_brightness REAL,
    max_brightness REAL,
    min_redness REAL,
    max_redness REAL,
    advice TEXT
)
''')

conn.commit()
conn.close()

print("Database tables created successfully!")