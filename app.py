import os
import sqlite3
from flask import Flask, g, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-123')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        if DATABASE_URL:
            import psycopg2
            db = g._database = psycopg2.connect(DATABASE_URL)
        else:
            db = g._database = sqlite3.connect('notes.db')
            db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cur = db.cursor()
    if DATABASE_URL:
        cur.execute('CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS notes (id SERIAL PRIMARY KEY, title TEXT, content TEXT, user_id INTEGER REFERENCES users(id))')
    else:
        cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT, user_id INTEGER)')
    db.commit()

@app.before_request
def before_request():
    init_db()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            return "مطلوب اسم وباسورد <a href='/register'>رجوع</a>"
        db = get_db()
        cur = db.cursor()
        hashed = generate_password_hash(password)
        try:
            if DATABASE_URL:
                cur.execute('INSERT INTO users (username, password_hash) VALUES (%s, %s)', (username, hashed))
            else:
                cur.execute('INSERT INTO users (username, password_hash) VALUES (?,?)', (username, hashed))
            db.commit()
            return redirect('/login')
        except:
            return "الاسم ده موجود قبل كده! <a href='/register'>جرب تاني</a>"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cur = db.cursor()
        if DATABASE_URL:
            cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        else:
            cur.execute('SELECT * FROM users WHERE username =?', (username,))
        user = cur.fetchone()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect('/')
        return "باسورد غلط <a href='/login'>حاول تاني</a>"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
    if DATABASE_URL:
        cur.execute('SELECT * FROM notes WHERE user_id = %s ORDER BY id DESC', (session['user_id'],))
    else:
        cur.execute('SELECT * FROM notes WHERE user_id =? ORDER BY id DESC', (session['user_id'],))
    notes = cur.fetchall()
    return render_template('index.html', notes=notes, username=session.get('username'))

@app.route('/add', methods=['POST'])
def add_note():
    if 'user_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
    if DATABASE_URL:
        cur.execute('INSERT INTO notes (title, content, user_id) VALUES (%s, %s, %s)', (request.form['title'], request.form['content'], session['user_id']))
    else:
        cur.execute('INSERT INTO notes (title, content, user_id) VALUES (?,?,?)', (request.form['title'], request.form['content'], session['user_id']))
    db.commit()
    return redirect('/')

@app.route('/delete/<int:id>', methods=['POST'])
def delete_note(id):
    if 'user_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
    if DATABASE_URL:
        cur.execute('DELETE FROM notes WHERE id = %s AND user_id = %s', (id, session['user_id']))
    else:
        cur.execute('DELETE FROM notes WHERE id =? AND user_id =?', (id, session['user_id']))
    db.commit()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)