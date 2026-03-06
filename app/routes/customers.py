from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db

bp = Blueprint('customers', __name__, url_prefix='/customers')

@bp.route('/')
def customer_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    cursor.execute('''
        SELECT c.*, 
            (SELECT COUNT(*) FROM appointments WHERE customer_id = c.id) as appt_count,
            (SELECT SUM(total) FROM orders WHERE customer_id = c.id) as total_spent
        FROM customers c
        WHERE c.company_id = ?
        ORDER BY c.created_at DESC
    ''', (company_id,))
    customers = cursor.fetchall()
    
    return render_template('customers.html', customers=customers)

@bp.route('/<int:id>')
def customer_detail(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customers WHERE id = ?', (id,))
    customer = cursor.fetchone()
    
    cursor.execute('SELECT * FROM appointments WHERE customer_id = ? ORDER BY start_at DESC', (id,))
    appointments = cursor.fetchall()
    
    cursor.execute('SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC', (id,))
    orders = cursor.fetchall()
    
    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for('customers.customer_list'))
        
    return render_template('customer_detail.html', customer=customer, appointments=appointments, orders=orders)
