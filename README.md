# Real Estate Bot (Telegram)

Telegram-бот для поиска/показа объектов недвижимости и сохранения избранного пользователя.

## Features
- Поиск объектов по фильтрам (город/район/цена/комнаты)
- Просмотр карточек объектов (фото/описание/ссылка)
- Избранное / история запросов
- Хранение данных в БД через db_handler

## Tech stack
Python, Telegram Bot API, SQLite/PostgreSQL (укажи что именно)

## Quickstart
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
python main.py
