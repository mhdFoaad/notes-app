import sqlite3
from flask import Flask, g, render_template, request, redirect
import os

app = Flask(__name__)
DATABASE = 'notes.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT)')
    db.commit()

# ده السطر السحري اللي ناقص عندك
@app.before_request
def before_request():
    init_db()

@app.route('/', methods=['GET'])
def index():
    db = get_db()
    notes = db.execute('SELECT * FROM notes ORDER BY id DESC').fetchall()
    return render_template('index.html', notes=notes)

@app.route('/add', methods=['POST'])
def add_note():
    title = request.form['title']
    content = request.form['content']
    db = get_db()
    db.execute('INSERT INTO notes (title, content) VALUES (?, ?)', (title, content))
    db.commit()
    return redirect('/')

@app.route('/delete/<int:id>', methods=['POST'])
def delete_note(id):
    db = get_db()
    db.execute('DELETE FROM notes WHERE id = ?', (id,))
    db.commit()
    return redirect('/')

# عشان يشتغل عندك لوكال
if __name__ == '__main__':
    app.run(debug=True)