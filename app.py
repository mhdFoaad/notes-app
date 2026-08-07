
import os, sys, traceback
from flask import Flask, render_template, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'v12-final')

DATABASE_URL = os.environ.get('DATABASE_URL')
IS_POSTGRES = DATABASE_URL and 'postgres' in DATABASE_URL.lower()

def get_db():
    if IS_POSTGRES:
        import psycopg2
        url = DATABASE_URL
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return psycopg2.connect(url)
    else:
        import sqlite3
        conn = sqlite3.connect('/tmp/notes.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
            cur.execute('CREATE TABLE IF NOT EXISTS notes (id SERIAL PRIMARY KEY, title TEXT, content TEXT, user_id INTEGER, pinned INTEGER DEFAULT 0, color TEXT DEFAULT '#ffffff', category TEXT DEFAULT '', position INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        else:
            cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
            cur.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT, user_id INTEGER, pinned INTEGER DEFAULT 0, color TEXT DEFAULT '#ffffff', category TEXT DEFAULT '', position INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"init_db error: {e}", file=sys.stderr)
        return False

init_db()

@app.route('/health')
def health():
    return f"OK V12 POSTGRES={IS_POSTGRES}", 200

@app.route('/init-db')
def init_db_route():
    ok = init_db()
    return f"{'OK' if ok else 'FAIL'} POSTGRES={IS_POSTGRES} <a href='/login'>Login</a>"

@app.route('/debug')
def debug():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        u = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM notes")
        n = cur.fetchone()[0]
        cur.close()
        conn.close()
        return f"POSTGRES={IS_POSTGRES} Users={u} Notes={n} <a href='/'>Home</a>"
    except Exception as e:
        return f"Error {e}"

@app.route('/clear-notes')
def clear_notes():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM notes")
        conn.commit()
        cur.close()
        conn.close()
        return "Cleared <a href='/'>Home</a>"
    except Exception as e:
        return str(e)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE user_id=%s ORDER BY id DESC', (session['user_id'],))
        else:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE user_id=? ORDER BY id DESC', (session['user_id'],))
        notes = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('index.html', notes=notes, username=session.get('username',''))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return f"Error: {e} <a href='/debug'>Debug</a>"

@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect('/login')
    title = request.form.get('title','').strip()
    content = request.form.get('content','').strip()
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('INSERT INTO notes (title, content, user_id) VALUES (%s,%s,%s)', (title, content, session['user_id']))
        else:
            cur.execute('INSERT INTO notes (title, content, user_id) VALUES (?,?,?)', (title, content, session['user_id']))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(e, file=sys.stderr)
    return redirect('/')

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('DELETE FROM notes WHERE id=%s AND user_id=%s', (id, session['user_id']))
        else:
            cur.execute('DELETE FROM notes WHERE id=? AND user_id=?', (id, session['user_id']))
        conn.commit()
        cur.close()
        conn.close()
    except: pass
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET','POST'])
def edit(id):
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE id=%s AND user_id=%s', (id, session['user_id']))
        else:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE id=? AND user_id=?', (id, session['user_id']))
        note = cur.fetchone()
        if not note:
            cur.close()
            conn.close()
            return redirect('/')
        if request.method == 'POST':
            title = request.form.get('title','').strip()
            content = request.form.get('content','').strip()
            if IS_POSTGRES:
                cur.execute('UPDATE notes SET title=%s, content=%s WHERE id=%s', (title, content, id))
            else:
                cur.execute('UPDATE notes SET title=?, content=? WHERE id=?', (title, content, id))
            conn.commit()
            cur.close()
            conn.close()
            return redirect('/')
        cur.close()
        conn.close()
        return render_template('edit.html', note=note)
    except:
        return redirect('/')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        from werkzeug.security import generate_password_hash
        password = generate_password_hash(request.form.get('password',''))
        try:
            conn = get_db()
            cur = conn.cursor()
            if IS_POSTGRES:
                cur.execute('INSERT INTO users (username,password) VALUES (%s,%s)', (username,password))
            else:
                cur.execute('INSERT INTO users (username,password) VALUES (?,?)', (username,password))
            conn.commit()
            cur.close()
            conn.close()
            return redirect('/login')
        except Exception as e:
            return f'Exists: {e} <a href="/login">Login</a>'
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        pwd = request.form.get('password','')
        try:
            conn = get_db()
            cur = conn.cursor()
            if IS_POSTGRES:
                cur.execute('SELECT id, username, password FROM users WHERE username=%s', (username,))
            else:
                cur.execute('SELECT id, username, password FROM users WHERE username=?', (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()
            from werkzeug.security import check_password_hash
            if user and check_password_hash(user[2], pwd):
                session['user_id'] = user[0]
                session['username'] = user[1]
                return redirect('/')
            else:
                return 'Wrong <a href="/login">Retry</a>'
        except Exception as e:
            return f'Error {e}'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
