# MGA Reklama backend

Django REST framework (django-parler, Jazzmin admin).

## Lokal ishga tushirish

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r req.txt
cp .env.example .env          # DJANGO_SECRET_KEY=dev-only, DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Videolarni admin orqali yuklash uchun `ffmpeg` (ffprobe bilan) o'rnatilgan bo'lishi kerak (`brew install ffmpeg`).

`.env` fayli git'ga tushmaydi. Har safar `git pull` dan keyin `python manage.py migrate` ni bajaring.

## Sozlamalar (muhit o'zgaruvchilari)

| O'zgaruvchi | Izoh |
|---|---|
| `DJANGO_SECRET_KEY` | **Majburiy.** Yo'q bo'lsa dastur ishga tushmaydi |
| `DJANGO_DEBUG` | `1`/`true`/`yes` bo'lsa yoqiladi, default o'chiq |
| `DJANGO_ALLOWED_HOSTS` | Vergul bilan ajratilgan hostlar (masalan `api.mgareklama.com`). DEBUG'da default `localhost,127.0.0.1` |
| `DJANGO_CORS_EXTRA_ORIGINS` | Ixtiyoriy qo'shimcha frontend originlari (vergul bilan) |
| `NUM_PROXIES` | gunicorn oldidagi proxy soni (default 1) |
| `EMAIL_*`, `CONTACT_NOTIFY_EMAILS`, `TELEGRAM_*` | Aloqa formasi xabarnomalari, `.env.example` ga qarang |

Tizim o'zgaruvchilari `.env` faylidagi qiymatlardan ustun turadi. Boshqa env fayl uchun `DJANGO_ENV_FILE=/yo'l/fayl.env`.

## Testlar

```bash
DJANGO_SECRET_KEY=test python manage.py test apps    # yoki .env mavjud bo'lsa: python manage.py test apps
python manage.py check --deploy
```

## Production (qisqacha)

- Server: `/etc/mgareklama/backend.env` fayli systemd `EnvironmentFile=` orqali o'qiladi (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, ...).
- DEBUG o'chiq bo'lganda `/media/` va `/static/` ni Django emas, nginx beradi.
- nginx quyidagi sarlavhalarni yuborishi shart: `X-Forwarded-Proto $scheme` (HTTPS aniqlash uchun) va `X-Forwarded-For $proxy_add_x_forwarded_for` (so'rov limiti uchun). HTTP -> HTTPS yo'naltirishni ham nginx qiladi.
- Deploy: `git pull`, `pip install -r req.txt`, `python manage.py migrate`, `python manage.py collectstatic --noinput`, gunicorn'ni qayta ishga tushirish.
