import psycopg2
from config import DB_CONFIG

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
    
    def save_analysis(self, user_id, data, result):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO analyses (user_id, location, area, price, type, result) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, data[0], float(data[1]), int(data[2]), data[3], result)  # Закрываем скобку тут
            )  # Добавили закрывающую скобку
            self.conn.commit()  # Теперь это на правильном уровне
    
    def close(self):
        self.conn.close()