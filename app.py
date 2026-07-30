from flask import Flask, render_template, request, redirect
import sqlite3

# 1. بنعمل نسخة من كلاس Flask، __name__ معناها "اعتبر الملف ده هو الأساس"
app = Flask(__name__)

# 2. دالة بتعمل اتصال بقاعدة البيانات
def get_db():
    conn = sqlite3.connect('notes.db')
    conn.row_factory = sqlite3.Row # عشان نتعامل مع الصفوف كأنها dict
    return conn

# 3. أول مرة السيرفر يشتغل، اعملي جدول للملاحظات
def init_db():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT)')
    db.commit()

@app.route('/', methods=['GET'])
def index():
    # ده اللي بيحصل لما حد يفتح http://127.0.0.1:5000/
    db = get_db()
    notes = db.execute('SELECT * FROM notes ORDER BY id DESC').fetchall()
    return render_template('index.html', notes=notes)

@app.route('/add', methods=['POST'])
def add_note():
    title = request.form['title'] # خد العنوان من الفورم
    content = request.form['content'] # خد المحتوى
    db = get_db()
    db.execute('INSERT INTO notes (title, content) VALUES (?, ?)', (title, content))
    db.commit()
    return redirect('/') # بعد الحفظ رجعه للصفحة الرئيسية

@app.route('/delete/<int:id>', methods=['POST'])
def delete_note(id):
    db = get_db()
    db.execute('DELETE FROM notes WHERE id = ?', (id,))
    db.commit()
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_note(id):
    db = get_db()
    
    # لو المستخدم داس حفظ بعد ما عدل
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        # UPDATE بيعدل صف موجود، مش بيضيف جديد
        db.execute('UPDATE notes SET title = ?, content = ? WHERE id = ?', (title, content, id))
        db.commit()
        return redirect('/')

    # لو هو لسه داخل على صفحة التعديل، هاتله البيانات القديمة
    else:
        note = db.execute('SELECT * FROM notes WHERE id = ?', (id,)).fetchone()
        return render_template('edit.html', note=note)

if __name__ == '__main__':
    init_db() # نجهز القاعدة قبل ما السيرفر يقوم
    app.run(debug=True, port=5000)