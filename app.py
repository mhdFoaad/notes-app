
import os, sys, traceback
import sqlite3
from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify

print(">>> V8 Ultimate Loading...", file=sys.stderr)
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'senior-secret-2026')

DATABASE_URL = os.environ.get('DATABASE_URL')
print(f">>> DATABASE_URL set: {bool(DATABASE_URL)}", file=sys.stderr)
IS_POSTGRES = DATABASE_URL and 'postgres' in DATABASE_URL.lower()

def get_db():
    if IS_POSTGRES:
        import psycopg2
        url = DATABASE_URL
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(url)
        return conn
    else:
        os.makedirs('/tmp', exist_ok=True)
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
            cur.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS color TEXT DEFAULT '#ffffff'")
            cur.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS category TEXT DEFAULT ''")
            cur.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS pinned INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0")
            cur.execute("UPDATE notes SET position = id WHERE position IS NULL OR position = 0")
        else:
            cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
            cur.execute("""CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY, title TEXT, content TEXT, user_id INTEGER,
                pinned INTEGER DEFAULT 0, color TEXT DEFAULT '#ffffff', category TEXT DEFAULT '', position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            for col_def in ["color TEXT DEFAULT '#ffffff'", "category TEXT DEFAULT ''", "pinned INTEGER DEFAULT 0", "position INTEGER DEFAULT 0"]:
                try: cur.execute(f"ALTER TABLE notes ADD COLUMN {col_def}")
                except: pass
        conn.commit()
        cur.close()
        conn.close()
        print(f">>> DB Init SUCCESS, IS_POSTGRES={IS_POSTGRES}", file=sys.stderr)
    except Exception as e:
        print(f">>> DB Init FAILED: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

init_db()

@app.route('/health')
def health():
    return f"OK - V8 Ultimate! DB: {'POSTGRES' if IS_POSTGRES else 'SQLITE'} - Ready!", 200

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')
@app.route('/manifest.json')
def manifest_route():
    return send_from_directory('static', 'manifest.json')

@app.route('/')
def index():
    print(">>> GET / - checking session", file=sys.stderr)
    if 'user_id' not in session:
        print(">>> No session, redirect to /login", file=sys.stderr)
        return redirect('/login')
    try:
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE user_id=%s ORDER BY pinned DESC, position DESC, id DESC', (session['user_id'],))
            notes = cur.fetchall()
        else:
            cur.execute('SELECT id, title, content, user_id, pinned, color, category, position FROM notes WHERE user_id=? ORDER BY pinned DESC, position DESC, id DESC', (session['user_id'],))
            notes = cur.fetchall()
        cur.close()
        conn.close()
        print(f">>> GET / success, notes={len(notes)}", file=sys.stderr)
    except Exception as e:
        print(f">>> GET / DB ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        notes = []
    return render_template('index.html', notes=notes, username=session.get('username',''))

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

@app.route('/reorder', methods=['POST'])
def reorder():
    if 'user_id' not in session:
        return jsonify({'ok': False}), 401
    data = request.get_json()
    order = data.get('order', [])
    try:
        conn = get_db()
        cur = conn.cursor()
        total = len(order)
        for idx, note_id in enumerate(order):
            pos = total - idx
            if IS_POSTGRES:
                cur.execute('UPDATE notes SET position=%s WHERE id=%s AND user_id=%s', (pos, note_id, session['user_id']))
            else:
                cur.execute('UPDATE notes SET position=? WHERE id=? AND user_id=?', (pos, note_id, session['user_id']))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Reorder error: {e}", file=sys.stderr)
    return jsonify({'ok': True})

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
    except Exception as e:
        print(f"Delete error: {e}", file=sys.stderr)
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
        traceback.print_exc(file=sys.stderr)
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
    except Exception as e:
        print(f"Pin error: {e}", file=sys.stderr)
    return redirect('/')

@app.route('/register', methods=['GET','POST'])
def register():
    print(f">>> {request.method} /register", file=sys.stderr)
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        pwd_raw = request.form.get('password','')
        from werkzeug.security import generate_password_hash
        password = generate_password_hash(pwd_raw)
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
            print(f">>> User {username} registered", file=sys.stderr)
            return redirect('/login')
        except Exception as e:
            print(f">>> Register error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return f'الاسم موجود او خطأ: {e}'
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    print(f">>> {request.method} /login", file=sys.stderr)
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
                print(f">>> Login success for {username}", file=sys.stderr)
                return redirect('/')
            else:
                print(f">>> Login failed for {username}", file=sys.stderr)
                return 'خطأ في الدخول - تأكد من الاسم والباسورد'
        except Exception as e:
            print(f">>> Login error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return f'خطأ: {e}'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
