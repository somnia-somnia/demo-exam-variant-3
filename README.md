# Ключ.на.старт — вариант 3

Модули 1–3: Python 3.11, **Django 5.2 + только MySQL**, серверный HTML,
общий CSS и 13 строк JavaScript. Сайт работает без интернет-соединения.
Публичная главная: слайдер → каталог LADA Vesta / Hyundai Creta / Toyota Camry.
Формы и кабинеты вынесены на отдельные страницы без фотографий.

## Запуск

Нужны Python 3.11 x64 Windows и запущенный MySQL. Пакеты для Python уже
находятся в `vendor/wheels`; MySQL является отдельной программой, Django его
не устанавливает. Один раз создайте пустую БД через клиент MySQL:

```sql
CREATE DATABASE rental CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
```

PowerShell из папки проекта, с учётными данными своего MySQL:

```powershell
python -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --no-index --find-links vendor/wheels -r requirements.txt
$env:MYSQL_DATABASE='rental'
$env:MYSQL_USER='root'
$env:MYSQL_PASSWORD='пароль вашего MySQL'
$env:MYSQL_HOST='127.0.0.1'
$env:MYSQL_PORT='3306'
.\.venv311\Scripts\python.exe app.py
```

Открыть [сайт](http://127.0.0.1:5000). **Admin / StartNET**.
При первом запуске Django создаёт таблицы и администратора. Существующие
записи не сбрасываются. `PORT` меняет HTTP-порт, `HOSTS` — разрешённые имена
хоста через запятую. Секрет сессии случайный для процесса: после перезапуска
нужно войти снова; аккаунты и заявки остаются в MySQL. Завершение — Ctrl+C.

В текущей рабочей папке уже подготовлены portable Python 3.11.9 и MySQL 8.4.13,
MySQL слушает `127.0.0.1:3307`. Для этой проверочной среды вместо команд выше:

```powershell
$env:MYSQL_PORT='3307'
$env:MYSQL_PASSWORD=(Get-Content tmp/mysql-credentials.json -Raw | ConvertFrom-Json).password
.\tmp\python311\python.exe app.py
```

`tmp/` с проверочными интерпретатором, сервером, данными и паролем не входит
в Git. После перезагрузки компьютера MySQL надо запустить заново. В этой
папке сохранён готовый сервер; его запуск без установки службы:

```powershell
$mysqlRoot=(Resolve-Path tmp/mysql-test/mysql-8.4.13-winx64).Path
$mysqlData=(Resolve-Path tmp/mysql-data).Path
Start-Process -FilePath "$mysqlRoot/bin/mysqld.exe" -WindowStyle Hidden -ArgumentList "--no-defaults --basedir=$mysqlRoot --datadir=$mysqlData --bind-address=127.0.0.1 --port=3307 --mysqlx=0"
```

Эта команда рассчитана на текущий путь без пробелов и выполняется только
когда порт 3307 свободен. Пароль в `tmp/mysql-credentials.json` не публикуется.
Для чистой копии Git требуется собственный заранее установленный сервер MySQL.

## Структура

```text
app.py                  запуск, создание таблиц, команды Django
config.py               настройки MySQL, сессий, CSRF, шаблонов
rental/models.py        три ORM-модели, PK/FK, уникальность логина, Admin
rental/forms.py         поля и обязательные серверные проверки
rental/views.py         основная логика, доступ, заявки, отзывы, статусы
templates/              base.html, home.html, form.html, bookings.html
static/                 общий CSS, короткий JS, локальные фото и Montserrat
vendor/wheels/          офлайн-зависимости Windows x64 Python 3.11
tools/import_legacy.py  необязательный одноразовый импорт старой SQLite
tests/                  функциональные, HTTP, браузерные проверки
docs/                   оригиналы, ER, SQL из MySQL, отчёты и статистика
module4/                прежние артефакты, в этой итерации не изменялись
```

Маршруты: `/`, `/register`, `/login`, `/bookings`, `/bookings/new`, `/admin`.
Формы и заявки работают без JS. Django ORM формирует параметризованные
запросы с явными именами столбцов. CSRF, роли, владелец заявки и завершение
аренды проверяются сервером; HTML отзывов экранируется. Изменение статуса
и проверка права на отзыв защищены транзакцией с блокировкой заявки.
Werkzeug оставлен для совместимости с прежними scrypt-хешами паролей.

Убраны произвольные верхние лимиты логина, пароля, ФИО, email и отзыва,
запрет второго отзыва и запрет возврата статуса. Обязательные минимум/форматы
сохранены. У email остаются ограничения составляющих корректного адреса,
у HTTP/СУБД — технические пределы. Прошлые даты разрешены согласно заданию.
В MySQL логин хранится как неограниченный TEXT, уникальный `login_key` —
SHA-256 от логина в нижнем регистре. Это позволяет не вводить длину логина
ради ограничения размера индекса MySQL.

## Старые данные

`instance/rental.db` сохранён без изменений; приложение больше его не читает.
В текущей рабочей MySQL его данные уже перенесены. Для другой пустой БД:

```powershell
.\.venv311\Scripts\python.exe tools/import_legacy.py C:\путь\rental.db
```

Инструмент открывает исходную SQLite только для чтения, сохраняет ID,
пароли-хеши, заявки и отзывы. При занятой целевой БД отказывается работать.
Он не нужен для нового сайта или обычного запуска.

## Проверка

При заданных выше переменных подключения:

```powershell
.\.venv311\Scripts\python.exe app.py test tests -v 2 --noinput
.\.venv311\Scripts\python.exe tests/verify_database.py
.\.venv311\Scripts\python.exe tests/report_statistics.py
```

Тестам нужны права CREATE/DROP DATABASE: они создают отдельные БД, а не
очищают пользовательскую. `python -m tests.browser_check` дополнительно
требует Edge и dev-пакет websocket-client. Эти зависимости не нужны сайту.

Все исходники сайта с `requirements.txt`: **11 988 символов Unicode с LF,
236 строк**, включая пробелы. Одноразовый импортёр отдельно: 1 085 символов.
Схему создаёт ORM; `docs/schema.mysql.sql` — сгенерированный отчёт, не код
запуска. Тесты, документация, готовые библиотеки и бинарные ресурсы отделены
от объёма ручного набора. Ограничение 12 000 проверяется автоматически.

[Требования и риски](docs/REQUIREMENTS.md), [проверки](docs/QA.md),
[точная статистика](docs/STATISTICS.md), [ER](docs/er.svg).

Модуль 4 и финальное руководство не изменялись. Старые `EXAM_REPRODUCTION.md`,
`EXAM_CHEATSHEET.md`, `CHATGPT_TUTOR_PROMPT.md` и отчёты прошлых итераций
описывают прежнюю версию и не являются инструкцией для этого кода.
