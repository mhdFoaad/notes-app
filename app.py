
import os, sys, traceback
from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'v11-final-2026')

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
            cur.execute("""CREATE TABLE IF NOT EXISTS notes (
                id SERIAL PRIMARY KEY, title TEXT, content TEXT, user_id INTEGER,
                pinned INTEGER DEFAULT 0, color TEXT DEFAULT '#ffffff', category TEXT DEFAULT '', position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        else:
            cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
            cur.execute("""CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY, title TEXT, content TEXT, user_id INTEGER,
                pinned INTEGER DEFAULT 0, color TEXT DEFAULT '#ffffff', category TEXT DEFAULT '', position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        cur.close()
        conn.close()
        return True, "OK"
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return False, str(e)

init_db()

@app.route('/health')
def health():
    return f"OK V11 - POSTGRES={IS_POSTGRES}", 200

@app.route('/init-db')
def init_db_route():
    ok, msg = init_db()
    return f"{'✅' if ok else '❌'} {msg}<br><a href='/login'>Login</a>"

@app.route('/debug')
def debug():
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute("SELECT COUNT(*) FROM users")
            u = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM notes")
            n = cur.fetchone()[0]
            cur.execute("SELECT id, username FROM users")
            users = cur.fetchall()
        else:
            u = n = 0
            users = []
        cur.close()
        conn.close()
        return f"DB: POSTGRES={IS_POSTGRES}<br>Users: {u}<br>Notes: {n}<br>Users List: {users}<br><br><a href='/'>Home</a> | <a href='/clear-notes'>Clear Notes</a> | <a href='/login'>Login</a>"
    except Exception as e:
        return f"Error: {e}"

@app.route('/clear-notes')
def clear_notes():
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute("DELETE FROM notes WHERE user_id IN (SELECT id FROM users WHERE username='mdfoaad')")
        else:
            cur.execute("DELETE FROM notes")
        conn.commit()
        cur.close()
        conn.close()
        return "✅ Notes cleared<br><a href='/'>Go Home</a>"
    except Exception as e:
        return f"Error: {e}"

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')
@app.route('/manifest.json')
def manifest_route():
    return send_from_directory('static', 'manifest.json')

@app.route('/')
def index():
    print(">>> GET / - START", file=sys.stderr, flush=True)
    try:
        if 'user_id' not in session:
            print(">>> No session, redirect to login", file=sys.stderr)
            return redirect('/login')
        print(f">>> Session user_id={session.get('user_id')}", file=sys.stderr)
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE user_id=%s ORDER BY pinned DESC, position DESC, id DESC', (session['user_id'],))
        else:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE user_id=? ORDER BY pinned DESC, position DESC, id DESC', (session['user_id'],))
        notes = cur.fetchall()
        cur.close()
        conn.close()
        print(f">>> Notes fetched: {len(notes)}", file=sys.stderr)
        return render_template('index.html', notes=notes, username=session.get('username',''))
    except Exception as e:
        print(f">>> ERROR in / : {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return f"<h2>Error in /: {e}</h2><pre>{traceback.format_exc()}</pre><a href='/debug'>Debug</a> | <a href='/clear-notes'>Clear</a> | <a href='/logout'>Logout</a>", 500

@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect('/login')
    title = request.form.get('title','').strip()
    content = request.form.get('content','').strip()
    color = request.form.get('color','').strip() or '#ffffff'
    category = request.form.get('category','').strip()
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('SELECT COALESCE(MAX(position),0)+1 FROM notes WHERE user_id=%s', (session['user_id'],))
            pos = cur.fetchone()[0]
            cur.execute('INSERT INTO notes (title, content, user_id, color, category, position) VALUES (%s,%s,%s,%s,%s,%s)', (title, content, session['user_id'], color, category, pos))
        else:
            cur.execute('SELECT COALESCE(MAX(position),0)+1 FROM notes WHERE user_id=?', (session['user_id'],))
            pos = cur.fetchone()[0]
            cur.execute('INSERT INTO notes (title, content, user_id, color, category, position) VALUES (?,?,?,?,?,?)', (title, content, session['user_id'], color, category, pos))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Add error: {e}", file=sys.stderr)
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
            color = request.form.get('color','').strip() or '#ffffff'
            category = request.form.get('category','').strip()
            if IS_POSTGRES:
                cur.execute('UPDATE notes SET title=%s, content=%s, color=%s, category=%s WHERE id=%s', (title, content, color, category, id))
            else:
                cur.execute('UPDATE notes SET title=?, content=?, color=?, category=? WHERE id=?', (title, content, color, category, id))
            conn.commit()
            cur.close()
            conn.close()
            return redirect('/')
        cur.close()
        conn.close()
        return render_template('edit.html', note=note)
    except Exception as e:
        print(f"Edit error: {e}", file=sys.stderr)
        return redirect('/')

@app.route('/pin/<int:id>', methods=['POST'])
def pin(id):
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('SELECT pinned FROM notes WHERE id=%s', (id,))
            row = cur.fetchone()
            new_pin = 0 if row[0]==1 else 1
            cur.execute('UPDATE notes SET pinned=%s WHERE id=%s', (new_pin, id))
        else:
            cur.execute('SELECT pinned FROM notes WHERE id=?', (id,))
            row = cur.fetchone()
            new_pin = 0 if row[0]==1 else 1
            cur.execute('UPDATE notes SET pinned=? WHERE id=?', (new_pin, id))
        conn.commit()
        cur.close()
        conn.close()
    except: pass
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
            return f'الاسم موجود: {e} <br><a href="/login">دخول</a>'
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
                return 'خطأ في الدخول<br><a href="/login">حاول تاني</a> | <a href="/register">سجل جديد</a>'
        except Exception as e:
            return f'خطأ: {e} <br><a href="/init-db">تهيئة</a>'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
