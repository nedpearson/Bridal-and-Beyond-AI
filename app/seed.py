import sqlite3
import datetime
from app import app
from database import DATABASE, init_db, get_db

def seed_data():
    conn = get_db()
    cursor = conn.cursor()
    print("Dropping existing tables to rebuild schema...")
    cursor.execute('PRAGMA foreign_keys = OFF;')
    tables = [
        "notification_jobs", "reminders", "notification_preferences",
        "pickup_items", "pickups", "commissions", "time_entries",
        "payment_ledger", "payment_plans", "order_items", "orders",
        "reservations", "product_variants", "products", "vendors",
        "appointment_checklists", "appointment_participants", "appointments", "services", "customers", "users", "locations", "companies"
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    cursor.execute('PRAGMA foreign_keys = ON;')

    print("Reinitializing database...")
    init_db()

    print("Inserting Companies...")
    cursor.execute('''
        INSERT INTO companies (id, name, domain, logo_url, primary_color, theme_bg)
        VALUES
        (1, 'I Do Bridal Couture', 'idobridalcouture.com', '//idobridalcouture.com/cdn/shop/files/IDO-Logo-Br-and-Cov-WHT-01a_2048x2048.png', '#aa8c66', 'dark'),
        (2, 'Proper & Co', 'properandcompany.com', '//properandcompany.com/cdn/shop/files/Proper_and_Co_white_logo_2048x2048.png', '#d3b798', 'dark')
    ''')

    print("Inserting Locations...")
    cursor.execute("INSERT INTO locations (company_id, name, address) VALUES (1, 'Baton Rouge', 'Baton Rouge, LA')")
    cursor.execute("INSERT INTO locations (company_id, name, address) VALUES (1, 'Covington', 'Covington, LA')")
    cursor.execute("INSERT INTO locations (company_id, name, address) VALUES (2, 'Main Boutique', 'Louisiana')")

    print("Inserting demo Users...")
    cursor.execute('''
        INSERT OR IGNORE INTO users (id, company_id, location_id, email, password_hash, role, first_name, last_name)
        VALUES 
        (1, 1, 1, 'demo@bridalops.com', 'pbkdf2:sha256:600000$mockhash', 'Owner', 'Jane', 'Doe'),
        (2, 1, 1, 'stylist@bridalops.com', 'pbkdf2:sha256:600000$mockhash', 'Stylist', 'Sarah', 'Smith'),
        (3, 2, 3, 'proper@bridalops.com', 'pbkdf2:sha256:600000$mockhash', 'Owner', 'Proper', 'Admin')
    ''')
    
    print("Inserting demo Customers...")
    wedding_date = (datetime.datetime.now() + datetime.timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO customers (company_id, location_id, first_name, last_name, email, phone, wedding_date)
        VALUES 
        (1, 1, 'Emily', 'Johnson', 'emily.j@example.com', '555-0101', ?),
        (2, 3, 'Jessica', 'Williams', 'jess.w@example.com', '555-0102', ?)
    ''', (wedding_date, wedding_date))
    
    print("Inserting demo Services...")
    cursor.execute('''
        INSERT INTO services (company_id, name, duration_minutes, default_price)
        VALUES 
        (1, 'Bridal Consultation', 90, 50.0),
        (1, 'First Fitting', 60, 0.0),
        (2, 'Couture Appointment', 120, 100.0)
    ''')
    
    print("Inserting demo Vendors & Products...")
    cursor.execute("INSERT INTO vendors (company_id, name, contact_name, email) VALUES (1, 'Stella York Bridal', 'Stella', 'stella@example.com')")
    cursor.execute("INSERT INTO vendors (company_id, name, contact_name, email) VALUES (2, 'Morilee', 'Madeline', 'madeline@example.com')")
    
    cursor.execute("INSERT INTO products (vendor_id, type, brand, name, sku, price) VALUES (1, 'Dress', 'Stella York', 'A-Line Lace Gown', 'SY-1001', 1500.00)")
    cursor.execute("INSERT INTO product_variants (product_id, size, color, sku_variant, on_hand_qty) VALUES (1, '10', 'Ivory', 'SY-1001-10-IV', 2)")
    
    print("Inserting demo Orders & Payments...")
    cursor.execute("INSERT INTO orders (id, company_id, location_id, customer_id, status, subtotal, total) VALUES (1, 1, 1, 1, 'Active', 1500.00, 1620.00)")
    cursor.execute("INSERT INTO order_items (order_id, product_variant_id, description, unit_price, line_total) VALUES (1, 1, 'Stella York A-Line Gown', 1500.00, 1500.00)")
    cursor.execute("INSERT INTO orders (id, company_id, location_id, customer_id, status, subtotal, total) VALUES (2, 2, 3, 2, 'Active', 2000.00, 2160.00)")
    
    # Ledger
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT INTO payment_ledger (order_id, customer_id, type, amount, method, occurred_at) VALUES (1, 1, 'Deposit', 810.00, 'Credit Card', ?)", (now,))
    
    print("Inserting demo Appointments...")
    apt_start_today1 = datetime.datetime.now().replace(hour=10, minute=0).strftime('%Y-%m-%d %H:%M:%S')
    apt_end_today1 = datetime.datetime.now().replace(hour=11, minute=30).strftime('%Y-%m-%d %H:%M:%S')
    
    apt_start_today2 = datetime.datetime.now().replace(hour=13, minute=0).strftime('%Y-%m-%d %H:%M:%S')
    apt_end_today2 = datetime.datetime.now().replace(hour=14, minute=0).strftime('%Y-%m-%d %H:%M:%S')
    
    apt_start_today3 = datetime.datetime.now().replace(hour=15, minute=30).strftime('%Y-%m-%d %H:%M:%S')
    apt_end_today3 = datetime.datetime.now().replace(hour=16, minute=30).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        INSERT INTO appointments (location_id, customer_id, service_id, assigned_staff_id, start_at, end_at, status)
        VALUES 
        (1, 1, 1, 2, ?, ?, 'Checked In'),
        (1, 1, 2, 2, ?, ?, 'Scheduled'),
        (3, 2, 3, 3, ?, ?, 'Scheduled')
    ''', (apt_start_today1, apt_end_today1, apt_start_today2, apt_end_today2, apt_start_today3, apt_end_today3))
    
    print("Inserting demo Pickups...")
    pickup_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pickup_date2 = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO pickups (company_id, location_id, order_id, customer_id, scheduled_at, status)
        VALUES 
        (1, 1, 1, 1, ?, 'Scheduled'),
        (1, 1, 1, 1, ?, 'Ready')
    ''', (pickup_date, pickup_date2))
    
    print("Inserting demo Payroll...")
    clock_in = (datetime.datetime.now() - datetime.timedelta(days=1)).replace(hour=9, minute=0).strftime('%Y-%m-%d %H:%M:%S')
    clock_out = (datetime.datetime.now() - datetime.timedelta(days=1)).replace(hour=17, minute=0).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT INTO time_entries (user_id, location_id, clock_in, clock_out, total_hours) VALUES (2, 1, ?, ?, 8.0)", (clock_in, clock_out))
    
    cursor.execute("INSERT INTO commissions (user_id, order_id, amount) VALUES (2, 1, 150.00)")
    
    conn.commit()
    # conn.close() handled by teardown
    print("Database seeding completed.")

if __name__ == '__main__':
    with app.app_context():
        seed_data()
