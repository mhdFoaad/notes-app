
import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'senior-fixed-key-2026')

DATABASE_URL = os.environ.get('DATABASE_URL')
IS_POSTGRES = DATABASE_URL and DATABASE_URL.startswith('postgres')

def get_db():
    if IS_POSTGRES:
        import psycopg2
        # fix for render postgres url that starts with postgres:// vs postgresql://
        url = DATABASE_URL
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(url)
        return conn
    else:
        conn = sqlite3.connect('notes.db')
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
                try:
                    cur.execute(f"ALTER TABLE notes ADD COLUMN {col_def}")
                except:
                    pass
            try:
                cur.execute("UPDATE notes SET position = id WHERE position IS NULL OR position = 0")
            except:
                pass
        conn.commit()
        cur.close()
        conn.close()
        print("DB init success, IS_POSTGRES:", IS_POSTGRES)
    except Exception as e:
        print("DB init failed:", e)
        # لا نوقف التطبيق لو الـ DB فشلت، عشان Render ما يعملش ERR_FAILED

init_db()

@app.route('/health')
def health():
    return "OK - App is running!", 200

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')
@app.route('/manifest.json')
def manifest_route():
    return send_from_directory('static', 'manifest.json')

@app.route('/')
def index():
    if 'user_id' not in session:
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
    except Exception as e:
        print("Index DB error:", e)
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
    conn = get_db()
    cur = conn.cursor()
    try:
        if IS_POSTGRES:
            cur.execute('SELECT COALESCE(MAX(position),0)+1 FROM notes WHERE user_id=%s', (session['user_id'],))
            pos = cur.fetchone()[0]
            cur.execute('INSERT INTO notes (title, content, user_id, color, category, position) VALUES (%s,%s,%s,%s,%s,%s)', (title, content, session['user_id'], color, category, pos))
        else:
            cur.execute('SELECT COALESCE(MAX(position),0)+1 FROM notes WHERE user_id=?', (session['user_id'],))
            pos = cur.fetchone()[0]
            cur.execute('INSERT INTO notes (title, content, user_id, color, category, position) VALUES (?,?,?,?,?,?)', (title, content, session['user_id'], color, category, pos))
        conn.commit()
    except Exception as e:
        print("Add error:", e)
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/reorder', methods=['POST'])
def reorder():
    if 'user_id' not in session:
        return jsonify({'ok': False}), 401
    data = request.get_json()
    order = data.get('order', [])
    conn = get_db()
    cur = conn.cursor()
    total = len(order)
    for idx, note_id in enumerate(order):
        pos = total - idx
        try:
            if IS_POSTGRES:
                cur.execute('UPDATE notes SET position=%s WHERE id=%s AND user_id=%s', (pos, note_id, session['user_id']))
            else:
                cur.execute('UPDATE notes SET position=? WHERE id=? AND user_id=?', (pos, note_id, session['user_id']))
        except Exception as e:
            print("Reorder error:", e)
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True})

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    conn = get_db()
    cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute('DELETE FROM notes WHERE id=%s AND user_id=%s', (id, session['user_id']))
    else:
        cur.execute('DELETE FROM notes WHERE id=? AND user_id=?', (id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET','POST'])
def edit(id):
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

@app.route('/pin/<int:id>', methods=['POST'])
def pin(id):
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
    return redirect('/')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = generate_password_hash(request.form.get('password',''))
        conn = get_db()
        cur = conn.cursor()
        try:
            if IS_POSTGRES:
                cur.execute('INSERT INTO users (username,password) VALUES (%s,%s)', (username,password))
            else:
                cur.execute('INSERT INTO users (username,password) VALUES (?,?)', (username,password))
            conn.commit()
            cur.close()
            conn.close()
            return redirect('/login')
        except Exception as e:
            print("Register error:", e)
            cur.close()
            conn.close()
            return 'الاسم موجود'
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        pwd = request.form.get('password','')
        conn = get_db()
        cur = conn.cursor()
        if IS_POSTGRES:
            cur.execute('SELECT id, username, password FROM users WHERE username=%s', (username,))
        else:
            cur.execute('SELECT id, username, password FROM users WHERE username=?', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user[2], pwd):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect('/')
        return 'خطأ في الدخول'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
