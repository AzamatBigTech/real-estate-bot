import psycopg2
from psycopg2 import sql, errors
from config import DB_CONFIG

class Database:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False  # Отключаем автокоммит для ручного управления транзакциями
        except psycopg2.Error as e:
            print(f"Ошибка подключения к базе данных: {e}")
            raise

    def save_analysis(self, user_id, data, result):
        try:
            # Проверка входных данных
            if len(data) != 4:
                raise ValueError("Неверное количество данных. Ожидается 4 элемента: Локация, Площадь, Цена, Тип.")

            location = data[0]
            area = float(data[1])  # Может вызвать ValueError
            price = int(data[2])   # Может вызвать ValueError
            property_type = data[3]

            with self.conn.cursor() as cur:
                cur.execute(
                    sql.SQL("""
                        INSERT INTO analyses (user_id, location, area, price, type, result)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """),
                    (user_id, location, area, price, property_type, result)
                )
                self.conn.commit()  # Фиксируем транзакцию
        except (ValueError, errors.Error) as e:
            self.conn.rollback()  # Откатываем транзакцию в случае ошибки
            print(f"Ошибка при сохранении анализа: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            print("Соединение с базой данных закрыто.")

    def __del__(self):
        self.close()  # Автоматически закрываем соединение при удалении объекта