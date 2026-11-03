# Экзамен без Jinja — страница 1/2

**150 минут: цель 120 + резерв 30.** Код 944c4b5:6 файлов,454 строк,20527 символов.
Сокращение 31.8%. План требует≈321 исправленного символа/мин; хронометраж не проведён.
Учебный материал:личные записи на экзамене — только если разрешены. Интернет/ИИ не нужны.

## Часы

| Минуты | Сделать |
|---|---|
|00–10|Окружение/Git/медиа/шрифты|
|10–15|db.py/schema.sql|
|15–39|app.py, проверка GET/api|
|39–53|static/index.html|
|53–66|static/script.js, первый рабочий UI|
|66–72|М 1:регистрация/заявка/Admin/ER/commit|
|72–84|М 2:CSS до 80,5 страниц/slider/ошибки/commit|
|84–87|М 3:FK/integrity/анимации/commit|
|87–112|М 4:grid/header до 93, Home до 100, Solutions до 108, prototype/save|
|112–120|Финальный сценарий/Git/передача|
|120–150|Резерв:исправления, повторный контроль, сдача|

## Команды — PowerShell из корня

```powershell
git init
git config user.name "Фамилия Имя"
git config user.email "student@exam.local"
git commit --allow-empty -m "M1: start"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links "D:\Public\wheels" -r requirements.txt
.\.venv\Scripts\python.exe -m py_compile app.py db.py
.\.venv\Scripts\python.exe app.py
```

Flask уже есть в разрешённом Python → использовать его. Путь wheels пример; подставить выданный.
requirements:Flask==3.1.2. Сайт 127.0.0.1:5000/login,**Admin/StartNET**. Restart после Python;
Ctrl+F5 после CSS/JS. Нет JS → секции ещё скрыты. Первый API:csrf48hex, user:null, rows[].

## Правила и защита

- users.id → bookings.user_id; bookings.id → reviews.booking_id(FK+UNIQUE). ER из реальной SQLite.
- login≥6 латиница/цифры, пароль≥8, ФИО кириллица/пробелы, email. Телефон 8(999)123-45-67.
- car:CARS, оплата:PAYMENTS, датаДД.ММ.ГГГГ. Разделители вводить вручную — маски удалены.
- Статусы:Новая → Идет аренда → Аренда завершена. Последний терминален.
- Владелец/роль только из g.user/БД. API отдаёт уже отобранные строки, не все записи браузеру.
- POST:FormData+csrf из /api. Успех 200JSON next → переход JS; ошибка 400/403/404/409 → output.
- template — обычный HTML, cloneNode копирует карточку. textContent не выполняет HTML отзыва.
- get/options/check — обычные функции JS/Python. Не писать Jinja или HTML-строки в Python.
- Слайдер 4 фото 960×600,3000ms, две стрелки 44px; фон/reduced-motion останавливают автомат.

<div style="break-after: page;"></div>

# Экзамен — страница 2/2

## «Таймыр» в Adobe XD Windows

File → Save As Local Document → module4/Группа-Таймыр.xd. **2 экрана 430×932**, первый стартовый.
Grid4×89, gap14, margin16, второй артборд X478. Roboto:R14/18, B14/18, B16/20, B28/34.
Текст полностью из выданного DOCX. Все зоны≥40×40; текст≥14px. PNG не заменяет .xd.
Фон#F5F8F8, teal#0E7583, текст#17363B, muted#536A6E, line#D5E3E5, белый.
Hover:pale#EAF3F4/текст#085966. Radius6 у кнопок,8 у карточек, нет теней.

| Объект | X, Y, W, H |
|---|---|
|Шапка; логотип|0,0,430,96;16,12,132,35.85|
|Меню Главная/Решения|16/222,48,192,40|
|Home поиск; заголовок|16,108,398,44;16,202,398,68|
|Фото; описание|16,282,398,110;16,408,398,108|
|Преимущества|X30, Y530/556/600, W384|
|CTA|16,648/700,398,44|
|Юридический текст; footer|16,772,398,36; Y820|
|Solutions ряд 1|X16/222, Y100,192×330|
|Ряд 2; ряд 3|Y440,192×276; Y726,192×158|
|Подробнее|X28/234, Y378/664/832,168×40|
|Footer|Y896, низ 914|

6 карточек:Studio, Server, Mobile, Embedded, стек, поддержка. Тексты не сокращать.
Меню Tap/Transition → нужный экран; две CTA и 6 Подробнее без переходов.
Меню Main Component → `+` → Hover State, изменить цвет, вернуть Default; Tap проверить после Hover.
Hover остальных кнопок — визуальное состояние, не переход. Preview туда/обратно, save/close/reopen.
Скрытый образец цвета сам не работает. Исходный .sketch не прошёл GUI-проверку.

## Финальный smoke

1. Гость → вход; неверная регистрация/пароль → ошибки. Driver01/12345678 входит.
2. A создаёт LADA, B в приватном окне Toyota. Каждый видит своё и в кабинете, и в /api.
3. Admin видит обе; B/admin403; фильтр; отзыв Новая/Идет 403, чужой 404, завершённый свой 200, повтор 409.
4. Пять страниц 390×844/desktop; все локальные ресурсы;4 слайда/стрелки; XD Preview/сохранение/reopen.
5. Реальные start/end commit каждого модуля, ER/схема/медиа/нативный файл в папке сдачи.

```powershell
git add .
git commit -m "exam: final checks"
git status --short
git log --oneline -10
git push -u origin HEAD
```

Push только в выданный remote/LAN. Local commit не равен сдаче. instance/.venv/secret.key вне Git.
Ошибка:пусто → Console/API/id;400POST → csrf;500SQL → поля/CHECK;404resource → имя; locked → закрыть GUI-транзакцию.
Не отключать доступ/CSRF/FK, не удалять финальную БД. Тесты/генератор не набирать в экзамен.
**Осталось 30:**save → главный пробел≤15 мин → проверки → сдача. **15:**одна критичная правка≤5 мин, затем
smoke/Git. **5:**только save → открытие → commit/передача, без массовых переделок.
