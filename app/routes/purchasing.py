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
    
    return render_template('purchasing.html', vendors=vendors, pos=pos)

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
