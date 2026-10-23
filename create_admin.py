import os

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import IntegrityError
from werkzeug.security import generate_password_hash

load_dotenv()

connection = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "college_events"),
)

username = input("Admin username: ").strip()
password = input("Admin password (at least 10 characters): ")

if len(password) < 10:
    connection.close()
    raise SystemExit("Password must have at least 10 characters.")

cursor = connection.cursor()

try:
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role)
        VALUES (%s, %s, 'admin')
        """,
        (username, generate_password_hash(password)),
    )
    connection.commit()
    print("Administrator account created.")
except IntegrityError:
    print("That username already exists. Run this file again with a different username.")
finally:
    cursor.close()
    connection.close()