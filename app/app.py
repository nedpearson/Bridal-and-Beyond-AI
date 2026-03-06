from flask import Flask, render_template, session, redirect, url_for, request, flash
import os
from database import init_db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-for-bridal-ops")

# Ensure database is initialized on startup
with app.app_context():
    init_db()

# Register Blueprints
from routes.customers import bp as customers_bp
from routes.appointments import bp as appointments_bp
from routes.inventory import bp as inventory_bp
from routes.purchasing import bp as purchasing_bp
from routes.payroll import bp as payroll_bp
from routes.orders import bp as orders_bp
from routes.pickups import bp as pickups_bp
from routes.reports import bp as reports_bp

app.register_blueprint(customers_bp)
app.register_blueprint(appointments_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(purchasing_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(pickups_bp)
app.register_blueprint(reports_bp)

@app.teardown_appcontext
def close_connection(exception):
    from flask import g
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.context_processor
def inject_company_context():
    """
    Globally injects the active company's branding into every Jinja template.
    If no company is active in the session, falls back to a default theme.
    """
    from database import get_db
    company = None
    all_companies = []
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Load all companies for the switcher dropdown
    cursor.execute("SELECT * FROM companies")
    all_companies = cursor.fetchall()
    
    if 'company_id' in session:
        cursor.execute("SELECT * FROM companies WHERE id = ?", (session['company_id'],))
        company = cursor.fetchone()
    
    if company:
        return dict(
            active_company=company,
            all_companies=all_companies,
            theme_color=company['primary_color'],
            theme_bg=company['theme_bg']
        )
    return dict(
        active_company=None,
        all_companies=all_companies,
        theme_color="#aa8c66", 
        theme_bg="dark"
    )

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Default to company ID 1 ('I Do Bridal Couture')
        session['user_id'] = 1
        session['company_id'] = 1
        session['role'] = 'Owner'
        session['name'] = 'Demo Admin'
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/switch_company/<int:company_id>', methods=['POST'])
def switch_company(company_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM companies WHERE id = ?", (company_id,))
    if cursor.fetchone():
        session['company_id'] = company_id
        flash("Company switched successfully.", "success")
    else:
        flash("Invalid company selected.", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    
    # Dashboard metrics
    cursor.execute('''
        SELECT COUNT(a.id) as cnt FROM appointments a
        JOIN customers c ON a.customer_id = c.id
        WHERE DATE(a.start_at) = DATE('now') AND c.company_id = ?
    ''', (company_id,))
    today_appts = cursor.fetchone()['cnt']
    
    cursor.execute('''
        SELECT COUNT(p.id) as cnt FROM pickups p
        JOIN orders o ON p.order_id = o.id
        WHERE p.status IN ('Scheduled', 'Ready') AND o.company_id = ?
    ''', (company_id,))
    pickups_due = cursor.fetchone()['cnt']
    
    cursor.execute('''
        SELECT SUM(o.total) - 
               COALESCE((SELECT SUM(amount) FROM payment_ledger WHERE order_id = o.id AND type IN ('Deposit', 'Installment', 'Final')), 0) +
               COALESCE((SELECT SUM(amount) FROM payment_ledger WHERE order_id = o.id AND type = 'Refund'), 0) as balance
        FROM orders o
        WHERE o.status != 'Cancelled' AND o.company_id = ?
    ''', (company_id,))
    row = cursor.fetchone()
    outstanding = row['balance'] if row and row['balance'] else 0.0
    
    cursor.execute('''
        SELECT COUNT(po.id) as cnt FROM purchase_orders po
        JOIN vendors v ON po.vendor_id = v.id
        WHERE po.status IN ('Submitted', 'Partially_Received') AND v.company_id = ?
    ''', (company_id,))
    po_count = cursor.fetchone()['cnt']
    
    # Today's schedule
    cursor.execute('''
        SELECT a.start_at, c.first_name || ' ' || c.last_name as customer_name, 
               s.name as service_name, u.first_name as stylist_name, a.status, c.wedding_date
        FROM appointments a
        JOIN customers c ON a.customer_id = c.id
        JOIN services s ON a.service_id = s.id
        LEFT JOIN users u ON a.assigned_staff_id = u.id
        WHERE DATE(a.start_at) = DATE('now') AND c.company_id = ?
        ORDER BY a.start_at ASC
    ''', (company_id,))
    schedule = cursor.fetchall()
        
    return render_template('dashboard.html',
                          today_appts=today_appts,
                          pickups_due=pickups_due,
                          outstanding=outstanding,
                          po_count=po_count,
                          schedule=schedule)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
