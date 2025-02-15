  import logging
  import os
  import sys
  import openai
  from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
  from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
  from config import TELEGRAM_TOKEN, OPENAI_API_KEY
  from db_handler import Database
  from cachetools import cached, TTLCache
  from io import BytesIO
  from reportlab.lib.pagesizes import letter
  from reportlab.pdfgen import canvas
  from reportlab.lib.utils import simpleSplit
  
  # Кэширование запросов
  cache = TTLCache(maxsize=100, ttl=300)
  
  # Логирование
  logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
  logger = logging.getLogger(__name__)
  
  # Проверка переменных окружения
  if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
      logger.error("Не указаны TELEGRAM_TOKEN или OPENAI_API_KEY в переменных окружения.")
      sys.exit(1)
  
  # Инициализация базы данных
  db = Database()
  
  # Команда /start
  async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
      keyboard = [[InlineKeyboardButton("Анализ объекта", callback_data="analyze")],
                  [InlineKeyboardButton("Сравнить объекты", callback_data="compare")]]
      reply_markup = InlineKeyboardMarkup(keyboard)
      await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
  
  # Обработка кнопок
  async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
      query = update.callback_query
      await query.answer()
  
      if query.data == "analyze":
          await query.message.reply_text("Введите данные в формате: Локация|Площадь|Цена|Тип объекта")
      elif query.data == "compare":
          await query.message.reply_text("Введите два объекта в формате:\nЛокация1|Площадь1|Цена1|Тип1\nЛокация2|Площадь2|Цена2|Тип2")
  
  # Обработка сообщений
  async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
      try:
          data = update.message.text.split("|")
          if len(data) != 4:
              await update.message.reply_text("Неверный формат. Используйте: Локация|Площадь|Цена|Тип")
              return
  
          analysis_result = await openai_analysis(tuple(data))
          investment_grade = calculate_investment_grade(analysis_result)
          db.save_analysis(update.message.from_user.id, data, analysis_result)
          pdf_buffer = await generate_pdf_report(analysis_result, investment_grade)
  
          response = f"""
  📊 **Аналитический отчет**:
  {analysis_result}
  
  💰 **Оценка инвестиционной привлекательности**: {investment_grade}/100
  Рекомендация: {"✅ Инвестировать" if investment_grade >= 70 else "❌ Рассмотреть другие варианты"}
          """
          await update.message.reply_text(response, parse_mode="Markdown")
          await update.message.reply_document(document=pdf_buffer, filename="report.pdf")
      except Exception as e:
          logger.error(f"Ошибка: {e}")
          await update.message.reply_text("Ошибка обработки запроса. Попробуйте еще раз.")
  
  # Генерация PDF-отчета
  async def generate_pdf_report(analysis_result: str, investment_grade: int) -> BytesIO:
      buffer = BytesIO()
      c = canvas.Canvas(buffer, pagesize=letter)
      text = c.beginText(72, 750)
      text.setFont("Helvetica", 12)
      lines = simpleSplit(analysis_result, "Helvetica", 12, 450)
      for line in lines:
          text.textLine(line)
      text.textLine(f"Оценка инвестиционной привлекательности: {investment_grade}/100")
      c.drawText(text)
      c.save()
      buffer.seek(0)
      return buffer
  
  # Анализ через OpenAI API
  @cached(cache)
  async def openai_analysis(data: tuple) -> str:
      prompt = f"""
      Проведи инвестиционный анализ недвижимости:
      Локация: {data[0]}
      Площадь: {data[1]} м²
      Цена: {data[2]} руб
      Тип: {data[3]}
  
      1. Рыночная стоимость
      2. Арендный потенциал
      3. Тренды района
      4. Риски инвестиций
      """
      try:
          response = openai.ChatCompletion.create(
              model="gpt-3.5-turbo",
              messages=[{"role": "system", "content": "Ты эксперт в анализе недвижимости."},
                        {"role": "user", "content": prompt}],
              max_tokens=1500
          )
          return response["choices"][0]["message"]["content"].strip()
      except Exception as e:
          logger.error(f"OpenAI API Error: {e}")
          return "Ошибка при запросе к OpenAI API"
  
  # Оценка инвестиционной привлекательности
  def calculate_investment_grade(analysis: str) -> int:
      grade = min(100, max(0, len(analysis) // 10))
      if "риск" in analysis.lower():
          grade -= 20
      if "потенциал" in analysis.lower():
          grade += 20
      return grade
  
  # Запуск бота
  if __name__ == "__main__":
      application = Application.builder().token(TELEGRAM_TOKEN).build()
      application.add_handler(CommandHandler("start", start))
      application.add_handler(CallbackQueryHandler(button_handler))
      application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
      
      PORT = int(os.environ.get("PORT", 5000))
      WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
  
      if WEBHOOK_URL:
          logger.info(f"Запуск бота с вебхуками на порту {PORT}...")
          application.run_webhook(
              listen="0.0.0.0", port=PORT, url_path=TELEGRAM_TOKEN,
              webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
          )
      else:
          logger.info("Запуск бота в режиме polling...")
          application.run_polling()
