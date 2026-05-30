# APG Backend

Backend حقيقي للتطوير المحلي يربط تطبيق APG بالمصادقة، قاعدة البيانات، التحليل، السجل، البلاغات، ولوحة الأدمن.

## التشغيل المحلي

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

سيتم إنشاء SQLite وبيانات التطوير تلقائيًا.

## حسابات التطوير

- user@apg.local / user123
- admin@apg.local / admin123

لا تستخدم هذه الحسابات في الإنتاج.

## دمج محرك Layers الأصلي

هذه النسخة لا تنشئ Backend ثاني منفصل. تم دمج ملف `layers` الذي أرسلته داخل هذا الـ backend، وEndpoint `/analysis/analyze` يستخدمه مباشرة عبر `apg_layers_engine.py`.

للتأكد أن المستخدم والأدمن مربوطان بنفس قاعدة البيانات، شغّل السيرفر ثم نفّذ:

```bash
python scripts/smoke_test.py http://127.0.0.1:5000
```

إذا ظهر السطر التالي فكل شيء شغال:

```text
✅ APG backend flow works: User analysis is stored and visible to Admin.
```

ملاحظة: أزرار Demo في التطبيق تحاول الآن تسجيل الدخول بالحسابات الحقيقية أولًا. إذا لم يكن السيرفر يعمل، ستدخل Offline Demo ولن تظهر نتائج المستخدم عند الأدمن لأنها لن تحفظ في DB.
