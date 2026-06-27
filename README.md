# Tapitapi Bot

Telegram-бот для акции Tapitapi: регистрация участников, загрузка чеков, проверка чеков через API, выдача билетов за бутылки вина Tapitapi и автоматические розыгрыши.

## Что делает бот

- Принимает фото чека от зарегистрированного пользователя.
- Сначала распознает чек через DeepSeek-OCR-2 и ищет позиции Tapitapi.
- Если Tapitapi не найден, отклоняет чек без обращения к API.
- Если Tapitapi найден, считывает QR-код через OpenCV, затем через `pyzbar`.
- Отправляет чек в API `proverkacheka.com`.
- Получает номенклатуру товаров из ответа API.
- Ищет Tapitapi в номенклатуре без учета регистра и с учетом похожих OCR-вариантов: `tapitapi`, `tapitani`, `тапитапи`, `тапитани`.
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

Инструкция ниже рассчитана на Windows 10/11 с NVIDIA GPU (например RTX 3090).

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

### 3. Установить ZBar для QR-кодов

Для `pyzbar` на Windows нужна библиотека ZBar.

Вариант 1 — через conda (проще):

```powershell
conda install -c conda-forge zbar
```

Вариант 2 — вручную:

1. Скачайте ZBar для Windows.
2. Положите `libzbar-64.dll` в папку, которая есть в `PATH`, или рядом с `python.exe` вашего окружения.

OpenCV QR читает QR и без ZBar, но fallback через `pyzbar` работает только если ZBar установлен.

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

### 5. Установить DeepSeek-OCR-2 для NVIDIA GPU

1. Установите драйвер NVIDIA и CUDA Toolkit, совместимые с PyTorch 2.6.
2. Установите зависимости модели:

```powershell
pip install -r requirements-deepseek.txt
```

3. При необходимости установите `flash-attn`, если сборка проходит на вашей системе:

```powershell
pip install flash-attn==2.7.3 --no-build-isolation
```

DeepSeek-OCR-2 загружается лениво: модель не занимает видеопамять при старте бота, а поднимается при проверке загруженного чека перед обращением к API.

### 6. Создать `.env`

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

DEEPSEEK_OCR_ENABLED=true
DEEPSEEK_OCR_DEVICE=cuda
DEEPSEEK_OCR_MODEL=deepseek-ai/DeepSeek-OCR-2
```

Токен API проверки чеков и пароль админки уже зашиты в `bot/config.py`.

### 7. Запустить бот

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
- `bot/services/proverkacheka.py` - работа с API проверки чеков.
- `bot/services/deepseek_ocr.py` - предварительный OCR-фильтр через DeepSeek-OCR-2.
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

Бот отправляет QR-строку чека (`qrraw`) в API только после OCR-проверки, что в чеке есть название, похожее на `tapitapi` или `тапитапи`. Это экономит суточный лимит API.

Билеты создаются только по позициям API, где название товара похоже на `tapitapi` или `тапитапи` без учета регистра.

Порядок распознавания:

1. DeepSeek-OCR-2 распознает чек и ищет строки номенклатуры с названием, похожим на `tapitapi` или `тапитапи`.
2. Если Tapitapi не найден, чек отклоняется без запроса к API.
3. QR-код читается через OpenCV `QRCodeDetector`.
4. Если OpenCV не справился, QR-код читается через `pyzbar`.
5. Если QR-код не прочитан, бот просит пользователя прислать фото, где QR-код крупно и четко виден.
6. Если QR прочитан, бот отправляет чек в API проверки чеков.
7. Количество билетов берется только из номенклатуры API. Если API не подтвердил позиции Tapitapi, чек отклоняется.

## Частые проблемы на Windows

### PostgreSQL не подключается

- Проверьте, что служба PostgreSQL запущена: `services.msc` -> `postgresql-x64-16`.
- Проверьте логин/пароль в `DATABASE_URL`.
- Проверьте, что база `tapitapi` создана.

### `psql` не найден

Добавьте `C:\Program Files\PostgreSQL\16\bin` в переменную окружения `PATH` и перезапустите PowerShell.

### Админка не открывается

Открывайте именно:

```text
http://localhost:8000/admin
```

Пароль: `secure_password`.

### OCR долго работает

Первый запуск DeepSeek-OCR-2 может занять 1-2 минуты: модель скачивается и грузится в видеопамять.
