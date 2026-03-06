import sqlite3

try:
    conn = sqlite3.connect('C:/Users/nedpe/.gemini/antigravity/scratch/Bridal-and-Beyond-AI/app/bridal_beyond.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.scheduled_date as "Date", '#' || o.id as "Order #", 
               c.first_name || ' ' || c.last_name as "Customer", p.status as "Status"
        FROM pickups p
        JOIN orders o ON p.order_id = o.id
        JOIN customers c ON o.customer_id = c.id
        WHERE p.status IN ('Scheduled', 'Ready') AND o.company_id = 1 AND (p.location_id = 0 OR 0 = 0)
        ORDER BY p.scheduled_date ASC
    ''')
    print(cursor.fetchall())
except Exception as e:
    print(f"ERROR: {e}")
