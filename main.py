import logging
import os
import sys
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
)
from config import TELEGRAM_TOKEN, DEEPSEEK_API_KEY
from db_handler import Database
from cachetools import cached, TTLCache
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка переменных окружения
if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    logger.error("Не указаны TELEGRAM_TOKEN или DEEPSEEK_API_KEY в переменных окружения.")
    sys.exit(1)

# Инициализация базы данных
db = Database()

# Кэширование запросов (100 запросов, хранение 5 минут)
cache = TTLCache(maxsize=100, ttl=300)

# Команда /start
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Анализ объекта", callback_data="analyze")],
        [InlineKeyboardButton("Сравнить объекты", callback_data="compare")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# ✅ Обработчик кнопок
async def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "analyze":
        await query.message.reply_text("Введите данные объекта в формате: Локация|Площадь|Цена|Тип объекта")
        context.user_data["awaiting_analysis"] = True
    elif query.data == "compare":
        await query.message.reply_text("Введите **2 или более объектов** в формате:\n\nЛокация|Площадь|Цена|Тип\nЛокация|Площадь|Цена|Тип")
        context.user_data["awaiting_comparison"] = True

# ✅ Обработчик ввода данных
async def handle_message(update: Update, context: CallbackContext):
    try:
        text = update.message.text
        lines = text.split("\n")

        # Обработка анализа одного объекта
        if "awaiting_analysis" in context.user_data:
            del context.user_data["awaiting_analysis"]

            if len(lines) != 1:
                await update.message.reply_text("Ошибка: введите **один объект** в формате: Локация|Площадь|Цена|Тип")
                return

            data = lines[0].split("|")
            if len(data) != 4:
                await update.message.reply_text("Неверный формат данных. Используйте: Локация|Площадь|Цена|Тип объекта")
                return

            analysis_result = await deepseek_analysis(data)
            investment_grade = calculate_investment_grade(analysis_result)

            db.save_analysis(update.message.from_user.id, data, analysis_result)
            pdf_buffer = await generate_pdf_report([analysis_result], [investment_grade])

            response = f"📊 **Аналитический отчет**:\n{analysis_result}\n💰 **Оценка инвестиционной привлекательности**: {investment_grade}/100"
            await update.message.reply_text(response)
            await update.message.reply_document(document=pdf_buffer, filename="report.pdf")
            return

        # Обработка сравнения нескольких объектов
        if "awaiting_comparison" in context.user_data:
            del context.user_data["awaiting_comparison"]

            if len(lines) < 2:
                await update.message.reply_text("Ошибка: введите **минимум 2 объекта** в формате:\nЛокация|Площадь|Цена|Тип")
                return

            analyses = []
            grades = []
            for line in lines:
                data = line.split("|")
                if len(data) != 4:
                    await update.message.reply_text(f"Ошибка в строке: `{line}`. Убедитесь, что формат: Локация|Площадь|Цена|Тип")
                    return

                analysis = await deepseek_analysis(data)
                grade = calculate_investment_grade(analysis)
                analyses.append(analysis)
                grades.append(grade)

            pdf_buffer = await generate_pdf_report(analyses, grades)

            comparison_result = "\n\n".join([f"🏡 **Объект {i+1}**:\n{analyses[i]}\n💰 Оценка: {grades[i]}/100" for i in range(len(analyses))])
            await update.message.reply_text(f"📊 **Сравнительный анализ объектов**:\n{comparison_result}")
            await update.message.reply_document(document=pdf_buffer, filename="comparison_report.pdf")
            return

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")

# ✅ Анализ через API DeepSeek (кэширование)
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

    response = requests.post(
        "https://api.deepseek.com/generate",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json={"prompt": prompt, "max_tokens": 1500}
    )

    if response.status_code == 200:
        return response.json().get("text", "Ошибка в анализе")
    else:
        logger.error(f"DeepSeek API Error: {response.status_code} - {response.text}")
        return "Ошибка при запросе к DeepSeek API"

# ✅ Оценка инвестиционной привлекательности
def calculate_investment_grade(analysis: str) -> int:
    grade = len(analysis) // 10  # Простая оценка по длине анализа
    if "риск" in analysis.lower():
        grade -= 20
    if "потенциал" in analysis.lower():
        grade += 20
    return min(100, max(0, grade))

# ✅ Генерация PDF-отчета
async def generate_pdf_report(analyses: list, grades: list) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(72, 750, "Сравнительный анализ недвижимости")

    y_position = 730
    for i in range(len(analyses)):
        c.drawString(72, y_position, f"🏡 Объект {i+1}")
        c.drawString(72, y_position - 20, analyses[i][:400])
        c.drawString(72, y_position - 40, f"💰 Оценка инвестиционной привлекательности: {grades[i]}/100")
        y_position -= 80

    c.save()
    buffer.seek(0)
    return buffer

# ✅ Запуск бота
if __name__ == "__main__":
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    application.run_polling()