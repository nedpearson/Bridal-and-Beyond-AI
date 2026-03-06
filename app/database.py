import sqlite3
import datetime
import json
import hashlib
from flask import g

DATABASE = 'bridal_beyond.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Create tables if they do not exist (data persists across restarts)
    # Re-enable foreign keys if disabled
    cursor.execute('PRAGMA foreign_keys = ON;')
        
    # ==========================================
    # CORE ENTITIES
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            domain TEXT,
            logo_url TEXT,
            primary_color TEXT DEFAULT '#aa8c66',
            theme_bg TEXT DEFAULT 'dark',
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            email TEXT,
            active BOOLEAN DEFAULT 1,
            FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Viewer', -- Owner, Manager, Stylist, Alterations, Cashier, Viewer
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            notes TEXT,
            wedding_date TIMESTAMP,
            partner_name TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT NOT NULL, -- e.g., Consultation, Fitting, Alterations, Pickup
            duration_minutes INTEGER NOT NULL,
            default_price REAL DEFAULT 0.0,
            buffer_minutes INTEGER DEFAULT 0,
            active BOOLEAN DEFAULT 1,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
    ''')

    # ==========================================
    # SCHEDULING
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            assigned_staff_id INTEGER,
            start_at TIMESTAMP NOT NULL,
            end_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'Scheduled', -- Scheduled, Checked_In, Completed, No_Show, Cancelled
            notes TEXT,
            created_by INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(service_id) REFERENCES services(id),
            FOREIGN KEY(assigned_staff_id) REFERENCES users(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointment_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            relation TEXT, -- e.g., Mother of Bride, Bridesmaid
            phone TEXT,
            notes TEXT,
            FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointment_checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            type TEXT NOT NULL, -- e.g., Fitting, Pickup
            items_json TEXT NOT NULL, -- JSON array of checklist items
            completed_by INTEGER,
            completed_at TIMESTAMP,
            FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
            FOREIGN KEY(completed_by) REFERENCES users(id)
        )
    ''')

    # ==========================================
    # INVENTORY & PURCHASING
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT NOT NULL,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            portal_url TEXT,
            notes TEXT,
            active BOOLEAN DEFAULT 1,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER,
            type TEXT NOT NULL, -- Dress, Accessory, Veil, Shoes
            brand TEXT,
            name TEXT NOT NULL,
            sku TEXT UNIQUE NOT NULL,
            cost REAL NOT NULL DEFAULT 0.0,
            price REAL NOT NULL DEFAULT 0.0,
            active BOOLEAN DEFAULT 1,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            size TEXT,
            color TEXT,
            sku_variant TEXT UNIQUE NOT NULL,
            on_hand_qty INTEGER DEFAULT 0,
            track_inventory BOOLEAN DEFAULT 1,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_variant_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            appointment_id INTEGER,
            reserve_from TIMESTAMP NOT NULL,
            reserve_to TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'Held', -- Held, Confirmed, Released, Converted_To_Sale
            notes TEXT,
            FOREIGN KEY(product_variant_id) REFERENCES product_variants(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(appointment_id) REFERENCES appointments(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expected_delivery TIMESTAMP,
            status TEXT DEFAULT 'Draft', -- Draft, Submitted, Partially_Received, Received, Cancelled
            total_cost REAL DEFAULT 0.0,
            notes TEXT,
            created_by INTEGER,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            product_variant_id INTEGER NOT NULL,
            qty_ordered INTEGER NOT NULL,
            qty_received INTEGER DEFAULT 0,
            unit_cost REAL NOT NULL,
            FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
            FOREIGN KEY(product_variant_id) REFERENCES product_variants(id)
        )
    ''')

    # ==========================================
    # SALES & PAYMENTS
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            customer_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Draft', -- Draft, Active, Fulfilled, Cancelled
            subtotal REAL DEFAULT 0.0,
            tax REAL DEFAULT 0.0,
            total REAL DEFAULT 0.0,
            wedding_date_snapshot TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_variant_id INTEGER,
            service_id INTEGER,
            description TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(product_variant_id) REFERENCES product_variants(id),
            FOREIGN KEY(service_id) REFERENCES services(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL UNIQUE,
            terms TEXT, -- e.g., "50% Deposit, 50% on Pickup", "Net 30"
            installment_count INTEGER DEFAULT 1,
            next_due_date TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    ''')

    # AUDITABLE LEDGER - APPEND ONLY
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            type TEXT NOT NULL, -- Deposit, Final, Installment, Refund, Fee
            amount REAL NOT NULL,
            method TEXT NOT NULL, -- Cash, Card, Check, ACH, Other
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reference TEXT,
            memo TEXT,
            created_by INTEGER,
            immutable_hash TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    ''')

    # ==========================================
    # PAYROLL & COMMISSIONS
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            clock_in TIMESTAMP NOT NULL,
            clock_out TIMESTAMP,
            total_hours REAL,
            approved BOOLEAN DEFAULT 0,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'Pending', -- Pending, Paid, Reversed
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
    ''')

    # ==========================================
    # PICKUPS
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pickups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            order_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            scheduled_at TIMESTAMP,
            status TEXT DEFAULT 'Scheduled', -- Scheduled, Ready, Picked_Up, No_Show, Rescheduled
            pickup_contact_name TEXT,
            pickup_contact_phone TEXT,
            notes TEXT,
            signed_at TIMESTAMP,
            signed_by TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pickup_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pickup_id INTEGER NOT NULL,
            order_item_id INTEGER NOT NULL,
            checklist_status BOOLEAN DEFAULT 0,
            FOREIGN KEY(pickup_id) REFERENCES pickups(id) ON DELETE CASCADE,
            FOREIGN KEY(order_item_id) REFERENCES order_items(id)
        )
    ''')

    # ==========================================
    # REMINDERS & NOTIFICATIONS
    # ==========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER UNIQUE,
            user_id INTEGER UNIQUE,
            email_opt_in BOOLEAN DEFAULT 1,
            sms_opt_in BOOLEAN DEFAULT 1,
            in_app_opt_in BOOLEAN DEFAULT 1,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL, -- Appointment, Balance_Due, Pickup, Alterations_Due
            reference_id INTEGER NOT NULL, -- ID of appointment, order, or pickup
            trigger_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'Pending' -- Pending, Sent, Failed, Cancelled
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_id INTEGER,
            channel TEXT NOT NULL, -- Email, SMS, In-App
            recipient TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT DEFAULT 'Queued', -- Queued, Processing, Sent, Failed
            error_log TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(reminder_id) REFERENCES reminders(id) ON DELETE SET NULL
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    print("Initializing Bridal and Beyond AI Database...")
    init_db()
    print("Database tables created successfully!")
