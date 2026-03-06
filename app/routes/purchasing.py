from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db

bp = Blueprint('purchasing', __name__, url_prefix='/purchasing')

@bp.route('/')
def vendor_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    
    # Get vendors
    cursor.execute('''
        SELECT v.*, 
            COUNT(po.id) as open_orders,
            SUM(po.total_cost) as total_spent
        FROM vendors v
        LEFT JOIN purchase_orders po ON v.id = po.vendor_id AND po.status IN ('Draft', 'Submitted', 'Partially_Received')
        WHERE v.company_id = ?
        GROUP BY v.id
        ORDER BY v.name ASC
    ''', (company_id,))
    vendors = cursor.fetchall()

    # Get recent POs
    cursor.execute('''
        SELECT po.*, v.name as vendor_name 
        FROM purchase_orders po
        JOIN vendors v ON po.vendor_id = v.id
        WHERE v.company_id = ?
        ORDER BY po.order_date DESC
        LIMIT 10
    ''', (company_id,))
    pos = cursor.fetchall()
    
    # KPIs for Drilldowns
    cursor.execute('''
        SELECT COUNT(po.id) as count, SUM(po.total_cost) as expected_cost
        FROM purchase_orders po
        JOIN vendors v ON po.vendor_id = v.id
        WHERE v.company_id = ? AND po.status != 'Received'
    ''', (company_id,))
    po_stats = cursor.fetchone()
    total_open_pos = po_stats['count'] if po_stats and po_stats['count'] else 0
    total_expected_cost = po_stats['expected_cost'] if po_stats and po_stats['expected_cost'] else 0
    total_active_vendors = len(vendors)
    
    return render_template('purchasing.html', 
                           vendors=vendors, 
                           pos=pos,
                           total_active_vendors=total_active_vendors,
                           total_open_pos=total_open_pos,
                           total_expected_cost=total_expected_cost)

@bp.route('/api/drilldown/<metric>')
def drilldown_api(metric):
    if 'user_id' not in session: return {"error": "Unauthorized"}, 401
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    
    if metric == 'active_vendors':
        cursor.execute('''
            SELECT name as "Vendor Name", contact_name as "Contact", email as "Email", phone as "Phone"
            FROM vendors WHERE company_id = ? ORDER BY name ASC
        ''', (company_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["Vendor Name", "Contact", "Email", "Phone"]}
        
    elif metric == 'open_orders':
        cursor.execute('''
            SELECT '#' || po.id as "PO #", v.name as "Vendor", po.order_date as "Order Date", po.expected_delivery as "Expected", po.status as "Status"
            FROM purchase_orders po
            JOIN vendors v ON po.vendor_id = v.id
            WHERE v.company_id = ? AND po.status != 'Received'
            ORDER BY po.order_date DESC
        ''', (company_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["PO #", "Vendor", "Order Date", "Expected", "Status"]}
        
    elif metric == 'expected_cost':
        cursor.execute('''
            SELECT '#' || po.id as "PO #", v.name as "Vendor", po.status as "Status", "$" || printf("%.2f", po.total_cost) as "Amount"
            FROM purchase_orders po
            JOIN vendors v ON po.vendor_id = v.id
            WHERE v.company_id = ? AND po.status != 'Received'
            ORDER BY po.total_cost DESC
        ''', (company_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {"total_records": len(rows), "data": rows, "columns": ["PO #", "Vendor", "Status", "Amount"]}
        
    return {"error": "Invalid metric"}, 400

@bp.route('/vendor/<int:id>')
def vendor_detail(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get vendor info
    cursor.execute('SELECT * FROM vendors WHERE id = ?', (id,))
    vendor = cursor.fetchone()
    
    if not vendor:
        flash("Vendor not found.", "error")
        return redirect(url_for('purchasing.vendor_list'))
        
    # Get PO history for this vendor
    cursor.execute('''
        SELECT * FROM purchase_orders 
        WHERE vendor_id = ? 
        ORDER BY order_date DESC
    ''', (id,))
    pos = cursor.fetchall()
    
    return render_template('vendor_detail.html', vendor=vendor, pos=pos)
