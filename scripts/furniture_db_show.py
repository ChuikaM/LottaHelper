import sqlite3

def view_database():
    """Просмотр данных из базы данных"""
    conn = sqlite3.connect('../db/furniture.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM furniture ORDER BY cost')
    rows = cursor.fetchall()
    
    print(f"{'ID'} {'Название'} {'Цена'} {'URL изображения'} {'URL мебели'} {'category'}")
    print("-" * 100)
    
    for row in rows:
        print(f"{row[0]:<5} {row[1]:<40} {row[2]:<10,} {row[3] or 'N/A'}, {row[4] or 'N/A'} {row[5]}")
    
    print(f"\nВсего записей: {len(rows)}")
    
    conn.close()

if __name__ == "__main__":
    view_database()