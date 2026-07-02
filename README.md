# Tapitapi Bot

Telegram-бот для акции Tapitapi: регистрация участников, загрузка чеков, проверка чеков через API, выдача билетов за бутылки вина Tapitapi и автоматические розыгрыши.

## Что делает бот

- Принимает фото чека от зарегистрированного пользователя.
- Считывает QR-код через OpenCV, затем через `pyzbar`.
- Отправляет чек в API `proverkacheka.com`.
- Получает номенклатуру товаров из ответа API.
- Ищет Tapitapi в номенклатуре без учета регистра и с учетом похожих вариантов: `tapitapi`, `tapitani`, `тапитапи`, `тапитани`.
- Создает один билет на каждую бутылку Tapitapi в чеке.
- Хранит связь: пользователь -> чек -> бутылка -> билет.
- Проводит автоматические розыгрыши и уведомляет победителей.

## Логика билетов

Один билет создается за одну бутылку Tapitapi из номенклатуры чека.

Примеры:

- В чеке 1 бутылка Tapitapi -> 1 билет.
- В чеке 3 бутылки Tapitapi -> 3 билета.
- В чеке нет Tapitapi -> чек отклоняется.

Количество билетов не ограничено.

Один и тот же чек нельзя загрузить повторно. Проверка уникальности идет по фискальным данным чека: ФН, ФД и ФП.

## Розыгрыши

Розыгрыши запускаются автоматически по московскому времени.

- Еженедельный: каждый понедельник в 12:00, 2 сертификата Ozon по 2000 руб.
- Ежемесячный: каждый первый понедельник месяца в 12:00, 5 сертификатов Ozon по 2000 руб.
- Финальный: 21.12.2026 в 12:00, главные призы.

Все активные билеты, созданные до момента розыгрыша, участвуют в розыгрыше.

Если билет выиграл, он получает статус `won` и больше не участвует в следующих розыгрышах. Если победитель не подтвердил получение приза за 72 часа, билет аннулируется.

## Запуск на Windows

Инструкция ниже рассчитана на Windows 10/11.

### 1. Установить Python

1. Скачайте Python 3.10 или 3.11 с [python.org](https://www.python.org/downloads/windows/).
2. При установке включите галочку **Add Python to PATH**.
3. Проверьте в PowerShell:

```powershell
python --version
pip --version
```

### 2. Установить PostgreSQL

1. Скачайте установщик PostgreSQL 15/16 с [postgresql.org/download/windows](https://www.postgresql.org/download/windows/).
2. Запустите установщик.
3. Запомните пароль суперпользователя `postgres`.
4. Порт оставьте `5432`.
5. Установите **pgAdmin 4** вместе с PostgreSQL, если предложат.

После установки PostgreSQL должен работать как служба Windows. Проверка:

```powershell
psql --version
```

Если `psql` не найден, добавьте в `PATH` папку вроде:

```text
C:\Program Files\PostgreSQL\16\bin
```

#### Создать базу и пользователя

Откройте **SQL Shell (psql)** или PowerShell и выполните:

```sql
CREATE USER bot_user WITH PASSWORD 'bot_pass';
CREATE DATABASE tapitapi OWNER bot_user;
GRANT ALL PRIVILEGES ON DATABASE tapitapi TO bot_user;
```

Через PowerShell это можно сделать так:

```powershell
psql -U postgres -c "CREATE USER bot_user WITH PASSWORD 'bot_pass';"
psql -U postgres -c "CREATE DATABASE tapitapi OWNER bot_user;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE tapitapi TO bot_user;"
```

Система попросит пароль пользователя `postgres`.

Строка подключения для бота:

```env
DATABASE_URL=postgresql+asyncpg://bot_user:bot_pass@localhost:5432/tapitapi
```

### 3. QR-коды: pyzbar на Windows

Пакета `zbar` в conda **нет**. Правильное имя — `pyzbar`.

Основной путь чтения QR — **OpenCV** (`QRCodeDetector`). Он работает без ZBar.

Fallback через `pyzbar` ставится так:

```powershell
pip install pyzbar
```

На Windows wheel `pyzbar` уже содержит `libzbar-64.dll` и `libiconv.dll`.

Через conda (опционально):

```powershell
conda install -c conda-forge pyzbar
```

Если при импорте `pyzbar` ошибка про `libzbar-64.dll`, установите **Visual C++ Redistributable 2013 (x64)**:

https://www.microsoft.com/en-us/download/details.aspx?id=40784

Скачайте `vcredist_x64.exe`, установите и перезапустите PowerShell.

Проверка:

```powershell
python -c "from pyzbar.pyzbar import decode; print('pyzbar OK')"
```

### 4. Создать виртуальное окружение

Из корня проекта:

```powershell
cd C:\path\to\tapitapi-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Если PowerShell блокирует активацию:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Можно использовать Anaconda/Miniconda вместо venv:

```powershell
conda create -n tapitapi python=3.10
conda activate tapitapi
pip install -r requirements.txt
```

### 5. Создать `.env`

В корне проекта создайте файл `.env`:

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789
DATABASE_URL=postgresql+asyncpg://bot_user:bot_pass@localhost:5432/tapitapi
TIMEZONE=Europe/Moscow
START_DATE=2026-06-01
MAIN_DRAW_DATE=2026-12-21
MAIN_DRAW_PRIZES=3
END_DATE=2026-12-28
PUBLIC_IP=185.189.44.204
```

Токен API проверки чеков и пароль админки уже зашиты в `bot/config.py`.

### 6. Запустить бот

```powershell
python main.py
```

После запуска:

- бот начнет принимать сообщения в Telegram;
- база создаст таблицы автоматически;
- админка будет доступна по адресу `http://localhost:8000/admin`;
- при открытии `http://localhost:8000/` бот перенаправит на админку.

Вход в админку:

- логин: любой;
- пароль: `secure_password`.

## Основные команды

- `/start` - регистрация и главное меню.
- `/mytickets` - список билетов пользователя.
- `/support` - сообщение в поддержку.

## Где лежат файлы

- `main.py` - точка запуска.
- `bot/config.py` - настройки проекта.
- `bot/handlers/receipt.py` - прием фото чека.
- `bot/services/proverkacheka.py` - QR-код и работа с API проверки чеков.
- `bot/services/receipt_validator.py` - проверка фото и уникальности чека.
- `bot/services/ticket_manager.py` - создание билетов.
- `bot/services/lottery_scheduler.py` - расписание и проведение розыгрышей.
- `bot/services/notification.py` - уведомления победителей.
- `bot/models/database.py` - таблицы базы данных.
- `templates/` - HTML-шаблоны админки.
- `media/` - сохраненные фото чеков.

## Важные настройки

`DATABASE_URL` должен быть именно в формате `postgresql+asyncpg://...`, потому что бот работает через async SQLAlchemy.

Если запускаете проект не из корня, укажите абсолютные пути в `.env`:

```env
MEDIA_ROOT=C:\path\to\tapitapi-bot\media
STATIC_DIR=C:\path\to\tapitapi-bot\static
TEMPLATES_DIR=C:\path\to\tapitapi-bot\templates
```

Обычно это не требуется: по умолчанию пути считаются от корня проекта.

## Проверка чеков

Для проверки используется `https://proverkacheka.com/api/v1/check/get`.

Бот отправляет QR-строку чека (`qrraw`) в API и получает номенклатуру.

Билеты создаются только по позициям API, где название товара похоже на `tapitapi` или `тапитапи` без учета регистра.

Порядок проверки:

1. QR-код читается через OpenCV `QRCodeDetector`.
2. Если OpenCV не справился, QR-код читается через `pyzbar`.
3. Если QR-код не прочитан, бот просит пользователя прислать фото, где QR-код крупно и четко виден.
4. Если QR прочитан, бот отправляет `qrraw` в API проверки чеков.
5. Если локально QR не прочитан или `qrraw` не сработал, бот отправляет фото чека как `qrfile`.
6. Количество билетов берется из номенклатуры API (`data.json.items`). Если API не подтвердил позиции Tapitapi, чек отклоняется.

## Частые проблемы на Windows

### PostgreSQL не подключается

- Проверьте, что служба PostgreSQL запущена: `services.msc` -> `postgresql-x64-16`.
- Проверьте логин/пароль в `DATABASE_URL`.
- Проверьте, что база `tapitapi` создана.

### `psql` не найден

Добавьте `C:\Program Files\PostgreSQL\16\bin` в переменную окружения `PATH` и перезапустите PowerShell.

### Админка работает на localhost, но не по публичному IP

Код уже слушает `0.0.0.0:8000`. Если `http://localhost:8000/admin` открывается, а `http://ВАШ_IP:8000/admin` — нет, почти всегда виноват **Windows Firewall**.

PowerShell **от администратора**:

```powershell
New-NetFirewallRule -DisplayName "Tapitapi Admin 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

Разрешите `python.exe` для частной и публичной сети:

1. `wf.msc` → «Правила для входящих подключений» → «Создать правило»
2. Программа → путь к `python.exe` в вашем conda/env
3. Разрешить подключение → отметить **Частная** и **Публичная**

Проверка на самом сервере:

```powershell
netstat -an | findstr 8000
curl http://127.0.0.1:8000/admin
curl http://185.189.44.204:8000/admin
```

Должно быть `0.0.0.0:8000` в состоянии `LISTENING`.

Проверка с телефона **без VPN** (другая сеть):

```text
http://185.189.44.204:8000/admin
```

`PUBLIC_IP` — для ссылок в логах админки и MinIO.

### Админка не открывается

Открывайте:

```text
http://localhost:8000/admin
http://ВАШ_БЕЛЫЙ_IP:8000/admin
```

Пароль: `secure_password`.

### `conda install zbar` — PackagesNotFoundError

Пакета `zbar` в conda нет. Используйте:

```powershell
pip install pyzbar
```

или:

```powershell
conda install -c conda-forge pyzbar
```
