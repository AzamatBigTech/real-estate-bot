import logging
import os
import sys
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from config import TELEGRAM_TOKEN, DEEPSEEK_API_KEY
from db_handler import Database
from cachetools import cached, TTLCache
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка переменных окружения
if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    logger.error("Не указаны TELEGRAM_TOKEN или DEEPSEEK_API_KEY в переменных окружения.")
    sys.exit(1)

# Инициализация базы данных
db = Database()

# Кэш для запросов к API
cache = TTLCache(maxsize=100, ttl=300)

# Команда /start
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Анализ объекта", callback_data="analyze")],
        [InlineKeyboardButton("Сравнить объекты", callback_data="compare")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# Обработка нажатия кнопок
async def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "analyze":
        await query.message.reply_text("Введите параметры объекта в формате:\n📍 Локация|📏 Площадь|💰 Цена|🏢 Тип объекта\n\nПример: Москва|50|10000000|Квартира")

    elif query.data == "compare":
        await query.message.reply_text("Отправьте данные для сравнения нескольких объектов через запятую:\n\nПример:\nМосква|50|10000000|Квартира, Санкт-Петербург|60|12000000|Квартира")

# Обработка пользовательского ввода
async def handle_message(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split("|")
        if len(data) != 4:
            await update.message.reply_text("❌ Неверный формат данных. Используйте: Локация|Площадь|Цена|Тип объекта")
            return

        analysis_result = await deepseek_analysis(data)
        investment_grade = calculate_investment_grade(analysis_result)

        # Сохранение в базу данных
        db.save_analysis(update.message.from_user.id, data, analysis_result)

        # Генерация PDF-отчета
        pdf_buffer = await generate_pdf_report(analysis_result, investment_grade)

        # Ответ пользователю
        response = f"""
📊 *Аналитический отчет:*
{analysis_result}

💰 *Оценка инвестиционной привлекательности:* {investment_grade}/100
🔹 Рекомендация: {"✅ Инвестировать" if investment_grade >= 70 else "⚠️ Рассмотреть другие варианты"}
        """
        await update.message.reply_text(response, parse_mode="Markdown")
        await update.message.reply_document(document=pdf_buffer, filename="report.pdf")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.")

# Генерация PDF-отчета
async def generate_pdf_report(analysis_result: str, investment_grade: int) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(72, 750, "Аналитический отчет по недвижимости")
    c.drawString(72, 730, analysis_result[:300])  # Ограничение длины текста
    c.drawString(72, 710, f"Оценка инвестиционной привлекательности: {investment_grade}/100")
    c.save()
    buffer.seek(0)
    return buffer

# Анализ через DeepSeek API
@cached(cache)
async def deepseek_analysis(data: list) -> str:
    prompt = f"""
    Проведи инвестиционный анализ объекта недвижимости:
    📍 Локация: {data[0]}
    📏 Площадь: {data[1]} м²
    💰 Цена: {data[2]} руб
    🏢 Тип: {data[3]}

    Проанализируй:
    1️⃣ Рыночную стоимость
    2️⃣ Арендный потенциал
    3️⃣ Тренды района
    4️⃣ Риски инвестиций
    """

    try:
        response = requests.post(
            "https://api.deepseek.com/generate",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"prompt": prompt, "max_tokens": 1500}
        )

        if response.status_code != 200:
            logger.error(f"DeepSeek API Error: {response.status_code} - {response.text}")
            return "❌ Ошибка при запросе к DeepSeek API. Попробуйте позже."

        response_json = response.json()
        if "text" not in response_json:
            logger.error(f"DeepSeek API вернул некорректный ответ: {response_json}")
            return "❌ Ошибка обработки данных. Попробуйте снова."

        return response_json["text"]

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при обращении к DeepSeek API: {e}")
        return "❌ Ошибка сети при обращении к DeepSeek API. Проверьте подключение."

    except Exception as e:
        logger.error(f"Неизвестная ошибка при анализе: {e}")
        return "❌ Внутренняя ошибка. Попробуйте позже."

# Оценка инвестиционной привлекательности
def calculate_investment_grade(analysis: str) -> int:
    grade = len(analysis) // 10
    if "риск" in analysis.lower():
        grade -= 20
    if "потенциал" in analysis.lower():
        grade += 20
    return min(100, max(0, grade))

# Запуск бота
if __name__ == "__main__":
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Использование вебхуков (если задан URL)
    PORT = int(os.environ.get("PORT", 5000))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

    if WEBHOOK_URL:
        logger.info(f"Запуск бота с вебхуками на порту {PORT}...")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        )
    else:
        logger.info("Запуск бота в режиме polling...")
        application.run_polling()