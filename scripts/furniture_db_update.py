import sqlite3
import re
import json
import os
from bs4 import BeautifulSoup
from pathlib import Path

def create_database():
    """Создает базу данных и таблицу для хранения данных о мебели"""
    db_path = Path('../db/furniture.db')
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS furniture (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            furniture_name TEXT NOT NULL,
            cost INTEGER NOT NULL,
            url_image TEXT,
            url_furniture TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    return conn

def parse_furniture_blocks(html_content):
    """Парсит блоки с информацией о мебели из HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    furniture_blocks = soup.find_all('div', class_='js-product')
    
    furniture_data = []
    
    for block in furniture_blocks:
        try:
            # Название мебели
            name_elem = block.find('div', class_='js-product-name')
            furniture_name = name_elem.text.strip() if name_elem else None
            
            # Стоимость
            price_elem = block.find('div', class_='js-product-price')
            if price_elem and price_elem.get('data-product-price-def'):
                cost = int(price_elem['data-product-price-def'])
            else:
                price_value = block.find('div', class_='js-product-price-val')
                if price_value:
                    cost = int(re.sub(r'\D', '', price_value.text))
                else:
                    cost = 0
            
            # URL изображения (берём первое изображение из карусели)
            img_elem = block.find('div', class_='js-product-img')
            url_image = img_elem['data-original'] if img_elem and img_elem.get('data-original') else None
            
            # URL мебели
            url_furniture = block.get('data-product-url')
            
            if furniture_name and url_furniture:
                furniture_data.append({
                    'furniture_name': furniture_name,
                    'cost': cost,
                    'url_image': url_image,
                    'url_furniture': url_furniture
                })
                
        except Exception as e:
            print(f"Ошибка при обработке блока: {e}")
            continue
    
    return furniture_data

def save_to_database(conn, furniture_data, category):
    """Сохраняет данные о мебели в базу данных с указанием категории"""
    cursor = conn.cursor()
    saved_count = 0
    
    for item in furniture_data:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO furniture 
                (furniture_name, cost, url_image, url_furniture, category)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                item['furniture_name'],
                item['cost'],
                item['url_image'],
                item['url_furniture'],
                category
            ))
            saved_count += 1
        except Exception as e:
            print(f"Ошибка при сохранении '{item['furniture_name']}': {e}")
    
    conn.commit()
    print(f"  ✓ Сохранено {saved_count} записей в категории '{category}'")
    return saved_count

def export_to_json(db_path='../db/furniture.db', output_file='../catalog/furniture.json', category=None, compact=True):
    """
    Экспортирует данные из базы данных в JSON файл
    
    Args:
        db_path: путь к файлу базы данных
        output_file: путь к выходному JSON файлу
        category: если указано, экспортирует только указанную категорию
        compact: если True, сохраняет без отступов и лишних пробелов
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Формируем SQL запрос с фильтрацией по категории при необходимости
        if category:
            cursor.execute('''
                SELECT id, furniture_name, cost, url_image, url_furniture, category 
                FROM furniture 
                WHERE category = ? 
                ORDER BY category, furniture_name
            ''', (category,))
        else:
            cursor.execute('''
                SELECT id, furniture_name, cost, url_image, url_furniture, category 
                FROM furniture 
                ORDER BY category, furniture_name
            ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        # Преобразуем данные в список словарей
        furniture_list = []
        for row in rows:
            furniture_list.append({
                'id': row[0],
                'furniture_name': row[1],
                'cost': row[2],
                'url_image': row[3],
                'url_furniture': row[4],
                'category': row[5]
            })
        
        # Создаём директорию для экспорта, если её нет
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Параметры для компактного или читаемого формата
        if compact:
            indent = None
            separators = (',', ':')
        else:
            indent = 2
            separators = (', ', ': ')
        
        # Сохраняем в JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'total_items': len(furniture_list),
                'categories': sorted(set(item['category'] for item in furniture_list)),
                'items': furniture_list
            }, f, ensure_ascii=False, indent=indent, separators=separators, sort_keys=False)
        
        size_kb = output_path.stat().st_size / 1024
        print(f"  ✓ Экспорт завершён: {len(furniture_list)} записей → '{output_file}' ({size_kb:.1f} KB)")
        if category:
            print(f"    Экспортирована категория: {category}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при экспорте в JSON: {e}")
        return False

def export_by_category(db_path='../db/furniture.db', output_dir='export/by_category', compact=True):
    """
    Экспортирует данные по отдельным файлам для каждой категории
    
    Args:
        compact: если True, сохраняет в компактном формате без отступов
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем список уникальных категорий
        cursor.execute('SELECT DISTINCT category FROM furniture ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not categories:
            print("  ⚠️ Нет данных для экспорта")
            return False
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        total_exported = 0
        for category in categories:
            if export_to_json(
                db_path=db_path,
                output_file=f'{output_dir}/{category.lower().replace(" ", "_")}.json',
                category=category,
                compact=compact
            ):
                # Подсчитываем количество экспортированных записей
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM furniture WHERE category = ?', (category,))
                count = cursor.fetchone()[0]
                conn.close()
                total_exported += count
        
        print(f"\n  ✓ Экспорт по категориям завершён: {total_exported} записей в {len(categories)} файлах")
        print(f"    Файлы сохранены в: '{output_dir}'")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при экспорте по категориям: {e}")
        return False

def extract_category_from_filename(filename):
    """Извлекает категорию из имени файла"""
    category = Path(filename).stem  # Получаем имя файла без расширения
    return category.capitalize()

def find_html_files(directory='html'):
    """Находит все .html файлы в указанной директории"""
    html_dir = Path(directory)
    
    if not html_dir.exists():
        print(f"❌ Директория '{directory}' не найдена")
        return []
    
    html_files = list(html_dir.glob('*.html'))
    
    if not html_files:
        print(f"⚠️ В директории '{directory}' не найдено .html файлов")
        return []
    
    print(f"✓ Найдено {len(html_files)} HTML файлов в директории '{directory}'")
    return sorted(html_files)

def process_html_file(html_path, conn):
    """Обрабатывает один HTML файл и сохраняет данные в базу"""
    try:
        with open(html_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        category = extract_category_from_filename(html_path.name)
        furniture_data = parse_furniture_blocks(html_content)
        
        if furniture_data:
            saved = save_to_database(conn, furniture_data, category)
            print(f"  Найдено: {len(furniture_data)} товаров")
            return saved
        else:
            print(f"  ⚠️ Товары не найдены")
            return 0
            
    except Exception as e:
        print(f"  ❌ Ошибка при обработке: {e}")
        return 0

def main():
    """Основная функция скрипта"""
    print("="*60)
    print("ЗАПУСК ПАРСЕРА МЕБЕЛИ")
    print("="*60)
    
    # Находим все HTML файлы в папке
    html_files = find_html_files('html')
    
    if not html_files:
        print("\nЗавершение работы.")
        return
    
    total_saved = 0
    conn = create_database()
    
    print("\nОбработка файлов:")
    print("-"*60)
    
    for html_path in html_files:
        print(f"\n📁 {html_path.name}")
        saved = process_html_file(html_path, conn)
        total_saved += saved
    
    conn.close()
    
    print("\n" + "="*60)
    print(f"✅ Итого сохранено: {total_saved} записей в базу данных")
    print("="*60)
    
    # Автоматический экспорт в компактном JSON формате
    print("\n📤 ЭКСПОРТ ДАННЫХ В JSON (компактный формат)")
    print("-"*60)
    export_to_json(compact=True)
    
    print("\n" + "="*60)
    print("✅ ПАРСИНГ И ЭКСПОРТ ЗАВЕРШЁН")
    print("="*60)

if __name__ == "__main__":
    main()