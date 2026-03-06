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
from routes.staff import bp as staff_bp

app.register_blueprint(customers_bp)
app.register_blueprint(appointments_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(purchasing_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(pickups_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(staff_bp)

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
    locations = []
    active_location = None
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Load all companies for the switcher dropdown
    cursor.execute("SELECT * FROM companies")
    all_companies = cursor.fetchall()
    
    if 'company_id' in session:
        cursor.execute("SELECT * FROM companies WHERE id = ?", (session['company_id'],))
        company = cursor.fetchone()
        
        # Load locations for this company
        cursor.execute("SELECT * FROM locations WHERE company_id = ? AND active = 1 ORDER BY name ASC", (session['company_id'],))
        locations = cursor.fetchall()
        
        # Load active location if set, otherwise 0 means "All Locations"
        loc_id = session.get('location_id', 0)
        if loc_id != 0:
            cursor.execute("SELECT * FROM locations WHERE id = ?", (loc_id,))
            active_location = cursor.fetchone()
    
    if company:
        return dict(
            active_company=company,
            all_companies=all_companies,
            companies=all_companies, # Provide fallback naming
            locations=locations,
            active_location=active_location,
            theme_color=company['primary_color'],
            theme_bg=company['theme_bg']
        )
    return dict(
        active_company=None,
        all_companies=all_companies,
        companies=all_companies,
        locations=locations,
        active_location=None,
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
        # Default to company ID 1 ('I Do Bridal Couture') and "All Locations" (0)
        session['user_id'] = 1
        session['company_id'] = 1
        session['location_id'] = 0
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
    # Verify the company exists
    cursor.execute("SELECT id FROM companies WHERE id = ?", (company_id,))
    if cursor.fetchone():
        session['company_id'] = company_id
        session['location_id'] = 0 # Reset location to "All" on company switch
        flash("Company switched successfully.", "success")
    else:
        flash("Invalid company selected.", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/switch_location/<int:location_id>', methods=['POST'])
def switch_location(location_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if location_id == 0:
        session['location_id'] = 0
        flash("Viewing all locations.", "success")
        return redirect(request.referrer or url_for('dashboard'))
        
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    # Verify the location exists and belongs to the active company
    cursor.execute("SELECT id FROM locations WHERE id = ? AND company_id = ?", (location_id, session.get('company_id')))
    if cursor.fetchone():
        session['location_id'] = location_id
        flash("Location switched successfully.", "success")
    else:
        flash("Invalid location selected.", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    location_id = session.get('location_id', 0)
    
    # Dashboard metrics
    cursor.execute('''
        SELECT COUNT(a.id) as cnt FROM appointments a
        JOIN customers c ON a.customer_id = c.id
        WHERE DATE(a.start_at) = DATE('now') AND c.company_id = ? AND (a.location_id = ? OR ? = 0)
    ''', (company_id, location_id, location_id))
    today_appts = cursor.fetchone()['cnt']
    
    cursor.execute('''
        SELECT COUNT(p.id) as cnt FROM pickups p
        JOIN orders o ON p.order_id = o.id
        WHERE p.status IN ('Scheduled', 'Ready') AND o.company_id = ? AND (p.location_id = ? OR ? = 0)
    ''', (company_id, location_id, location_id))
    pickups_due = cursor.fetchone()['cnt']
    
    cursor.execute('''
        SELECT SUM(o.total) - 
               COALESCE((SELECT SUM(amount) FROM payment_ledger WHERE order_id = o.id AND type IN ('Deposit', 'Installment', 'Final')), 0) +
               COALESCE((SELECT SUM(amount) FROM payment_ledger WHERE order_id = o.id AND type = 'Refund'), 0) as balance
        FROM orders o
        WHERE o.status != 'Cancelled' AND o.company_id = ? AND (o.location_id = ? OR ? = 0)
    ''', (company_id, location_id, location_id))
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
        WHERE DATE(a.start_at) = DATE('now') AND c.company_id = ? AND (a.location_id = ? OR ? = 0)
        ORDER BY a.start_at ASC
    ''', (company_id, location_id, location_id))
    schedule = cursor.fetchall()
        
    return render_template('dashboard.html',
                          today_appts=today_appts,
                          pickups_due=pickups_due,
                          outstanding=outstanding,
                          po_count=po_count,
                          schedule=schedule)

@app.route('/api/dashboard/drilldown/<metric>')
def dashboard_drilldown(metric):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
        
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    location_id = session.get('location_id', 0)
    
    if metric == 'appointments_today':
        cursor.execute('''
            SELECT a.start_at as "Time", c.first_name || ' ' || c.last_name as "Customer", 
                   s.name as "Service", COALESCE(u.first_name, 'Unassigned') as "Stylist", 
                   a.status as "Status"
            FROM appointments a
            JOIN customers c ON a.customer_id = c.id
            JOIN services s ON a.service_id = s.id
            LEFT JOIN users u ON a.assigned_staff_id = u.id
            WHERE DATE(a.start_at) = DATE('now') AND c.company_id = ? AND (a.location_id = ? OR ? = 0)
            ORDER BY a.start_at ASC
        ''', (company_id, location_id, location_id))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["Time", "Customer", "Service", "Stylist", "Status"]}
        
    elif metric == 'pickups_due':
        cursor.execute('''
            SELECT p.scheduled_at as "Date", '#' || o.id as "Order #", 
                   c.first_name || ' ' || c.last_name as "Customer", p.status as "Status"
            FROM pickups p
            JOIN orders o ON p.order_id = o.id
            JOIN customers c ON o.customer_id = c.id
            WHERE p.status IN ('Scheduled', 'Ready') AND o.company_id = ? AND (p.location_id = ? OR ? = 0)
            ORDER BY p.scheduled_at ASC
        ''', (company_id, location_id, location_id))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["Date", "Order #", "Customer", "Status"]}
        
    elif metric == 'outstanding_balances':
        cursor.execute('''
            SELECT '#' || order_id as "Order #", customer as "Customer", status as "Status", 
                   "$" || printf("%.2f", balance) as "Balance"
            FROM (
                SELECT o.id as order_id, c.first_name || ' ' || c.last_name as customer, o.status,
                       o.total - 
                       COALESCE((SELECT SUM(amount) FROM payment_ledger WHERE order_id = o.id AND type IN ('Deposit', 'Installment', 'Final')), 0) +
                       COALESCE((SELECT SUM(amount) FROM payment_ledger WHERE order_id = o.id AND type = 'Refund'), 0) as balance
                FROM orders o
                JOIN customers c ON o.customer_id = c.id
                WHERE o.status != 'Cancelled' AND o.company_id = ? AND (o.location_id = ? OR ? = 0)
            )
            WHERE balance > 0
            ORDER BY balance DESC
        ''', (company_id, location_id, location_id))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["Order #", "Customer", "Status", "Balance"]}
        
    elif metric == 'awaiting_receiving':
        cursor.execute('''
            SELECT '#' || po.id as "PO #", v.name as "Vendor", po.order_date as "Order Date", 
                   po.expected_delivery as "Expected", po.status as "Status"
            FROM purchase_orders po
            JOIN vendors v ON po.vendor_id = v.id
            WHERE po.status IN ('Submitted', 'Partially_Received') AND v.company_id = ?
            ORDER BY po.order_date DESC
        ''', (company_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["PO #", "Vendor", "Order Date", "Expected", "Status"]}
        
    return {"error": "Invalid metric"}, 400

@app.route('/api/drilldown/<type>/<int:id>')
def universal_drilldown(type, id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
        
    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    
    if type == 'appointment':
        cursor.execute('''
            SELECT a.start_at as "Time", a.end_at as "End", s.name as "Service", 
                   COALESCE(u.first_name, 'Unassigned') as "Stylist", a.status as "Status",
                   a.notes as "Notes"
            FROM appointments a
            JOIN services s ON a.service_id = s.id
            LEFT JOIN users u ON a.assigned_staff_id = u.id
            WHERE a.id = ?
        ''', (id,))
        rows = [dict(row) for row in cursor.fetchall()]
        if not rows:
             return {"error": "Appointment not found"}, 404
        return {"total_records": len(rows), "data": rows, "columns": ["Time", "End", "Service", "Stylist", "Status", "Notes"]}
        
    elif type == 'order':
        # Retrieve Order items
        cursor.execute('''
            SELECT p.name as "Item", pv.size as "Size", pv.color as "Color", 
                   oi.quantity as "Qty", "$" || printf("%.2f", oi.unit_price) as "Unit Price", 
                   "$" || printf("%.2f", oi.quantity * oi.unit_price) as "Total"
            FROM order_items oi
            JOIN product_variants pv ON oi.product_variant_id = pv.id
            JOIN products p ON pv.product_id = p.id
            WHERE oi.order_id = ?
        ''', (id,))
        items = [dict(row) for row in cursor.fetchall()]
        
        # Retrieve payment ledger
        cursor.execute('''
            SELECT date as "Date", type as "Type", method as "Method", 
                   "$" || printf("%.2f", amount) as "Amount", notes as "Notes"
            FROM payment_ledger
            WHERE order_id = ?
            ORDER BY date ASC
        ''', (id,))
        payments = [dict(row) for row in cursor.fetchall()]
        
        # Combine them intelligently or just return items. For simplicity and because we only support one table format easily:
        # We will return items here, but a dedicated modal could display both. 
        # To adapt to the universal modal, we will return items.
        return {"total_records": len(items), "data": items, "columns": ["Item", "Size", "Color", "Qty", "Unit Price", "Total"]}
        
    elif type == 'product':
        cursor.execute('''
            SELECT pv.sku_variant as "SKU", pv.size as "Size", pv.color as "Color", 
                   pv.on_hand_qty as "In Stock", CASE WHEN pv.track_inventory THEN 'Yes' ELSE 'No' END as "Tracked"
            FROM product_variants pv
            WHERE pv.product_id = ?
        ''', (id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["SKU", "Size", "Color", "In Stock", "Tracked"]}
        
    elif type == 'po':
        cursor.execute('''
            SELECT p.name as "Product", pv.sku_variant as "SKU", 
                   poi.qty_ordered as "Ordered", poi.qty_received as "Received", 
                   "$" || printf("%.2f", poi.unit_cost) as "Cost",
                   "$" || printf("%.2f", poi.qty_ordered * poi.unit_cost) as "Total"
            FROM purchase_order_items poi
            JOIN product_variants pv ON poi.product_variant_id = pv.id
            JOIN products p ON pv.product_id = p.id
            WHERE poi.purchase_order_id = ?
        ''', (id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["Product", "SKU", "Ordered", "Received", "Cost", "Total"]}
        
    elif type == 'pickup':
         cursor.execute('''
            SELECT p.pickup_contact_name as "Contact", p.pickup_contact_phone as "Phone",
                   p.signed_at as "Signed At", p.signed_by as "Signed By", p.notes as "Notes"
            FROM pickups p
            WHERE p.id = ?
         ''', (id,))
         rows = [dict(row) for row in cursor.fetchall()]
         return {"total_records": len(rows), "data": rows, "columns": ["Contact", "Phone", "Signed At", "Signed By", "Notes"]}

    return {"error": "Invalid drilldown type"}, 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
