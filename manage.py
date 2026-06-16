"""Small management CLI.

    python manage.py initdb              # create + seed the database
    python manage.py reset               # wipe and re-create the database
    python manage.py admin <username>    # grant admin to an existing player
    python manage.py mkadmin <user> <pw> # create a new admin player
"""
import sys
import os

import db
from werkzeug.security import generate_password_hash
from game import now, ts


def initdb():
    db.init_db(seed=True)
    print("Database initialised and seeded.")


def reset():
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init_db(seed=True)
    print("Database reset.")


def make_admin(username):
    con = db.raw_connection()
    cur = con.execute("UPDATE users SET is_admin=1 WHERE username=?", (username,))
    con.commit()
    print("Granted admin." if cur.rowcount else "No such user.")
    con.close()


def create_admin(username, password):
    con = db.raw_connection()
    try:
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "INSERT INTO users(username,password_hash,is_admin,last_active) VALUES (?,?,1,?)",
            (username, generate_password_hash(password), ts(now())))
        uid = cur.lastrowid
        con.execute("INSERT INTO players(user_id,energy_ts,nerve_ts,health_ts) VALUES (?,?,?,?)",
                    (uid, ts(now()), ts(now()), ts(now())))
        con.commit()
        print(f"Admin '{username}' created.")
    except Exception as e:
        con.rollback()
        print("Failed:", e)
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "initdb":
        initdb()
    elif cmd == "reset":
        reset()
    elif cmd == "admin" and len(sys.argv) == 3:
        make_admin(sys.argv[2])
    elif cmd == "mkadmin" and len(sys.argv) == 4:
        create_admin(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
