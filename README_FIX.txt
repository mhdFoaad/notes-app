
# FIX للـ ERR_FAILED ومسح اليوزرز

## المشكلتين اللي في الصورة:

1- This site can't be reached + All logs تظهر Python 3.14.3
   السبب: Render نزل Python 3.14 الجديد جدا، ومكتبة psycopg2-binary 2.9.9 لا تدعمه في بعض الحالات + لا يوجد health check.

2- كل تحديث اليوزر يتمسح
   السبب: انت بتستخدم SQLite (notes.db) وده ملف محلي. Render يمسح كل الملفات مع كل Deploy لان الـ filesystem مؤقت!

## الحل:

### A- runtime.txt
ملف يخبر Render يستخدم Python 3.11.11 المستقر.

### B- requirements.txt بدون تثبيت اصدار
حتى يتوافق مع اي Python.

### C- render.yaml
يخبر Render انشئ Postgres مجاني واربطه تلقائيا. DATABASE_URL سيتم حقنه تلقائيا.

### D- تعديل app.py
- اضفنا /health عشان Render يعرف ان التطبيق شغال
- init_db لا يوقف التطبيق لو فشل
- اصلاح postgres:// vs postgresql://

### خطوات التركيب:
1- احذف كل ملفات المشروع القديم وضع ملفات هذا الـ ZIP مكانها
2- git add . && git commit -m "fix render deploy" && git push
3- ادخل Render Dashboard -> New + -> Blueprint -> اختر repo -> سيتم انشاء Web + Postgres تلقائيا
   او لو عندك Service موجود: Environment -> Add -> DATABASE_URL من الـ Postgres الداخلي + PYTHON_VERSION=3.11.11
4- بعد الـ Deploy ادخل /health يجب ان ترى OK
5- سجل يوزر جديد - الان لن يمسح بعد التحديث لانه في Postgres!

