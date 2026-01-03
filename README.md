# Real Estate Bot (Telegram)

Telegram-бот на Python для поиска и просмотра объектов недвижимости.

## Что делает проект
Бот принимает сообщения пользователя в Telegram и показывает информацию
об объектах недвижимости. Данные обрабатываются и сохраняются в базе данных.

Проект создан как практический пример Python-приложения с работой
с внешним API и базой данных.

## Основные возможности
- Обработка сообщений пользователей в Telegram
- Показ информации об объектах недвижимости
- Работа с базой данных через отдельный модуль
- Простая структура проекта

## Стек технологий
- Python
- Telegram Bot API
- Database: SQLite / PostgreSQL (укажи что используешь)

## Как запустить проект локально

### 1. Скачать проект
```bash
git clone https://github.com/AzamatBigTech/real-estate-bot.git
cd real-estate-bot

2. Установить зависимости
python -m venv venv
source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
3. Запустить бота
Структура проекта
main.py — точка входа, логика Telegram-бота
db_handler.py — работа с базой данных
config.py — конфигурация проекта
requirements.txt — зависимости

Что можно улучшить дальше
Вынести секреты в .env
Добавить тесты (pytest)
Добавить CI (GitHub Actions)
Улучшить обработку ошибок

Автор
Azamat Mukazhanov
