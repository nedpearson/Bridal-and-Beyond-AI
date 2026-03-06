from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
import hashlib

bp = Blueprint('orders', __name__, url_prefix='/orders')

@bp.route('/')
def order_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    location_id = session.get('location_id', 0)
    
    # Get all active orders and their balances
    cursor.execute('''
        SELECT o.*, c.first_name, c.last_name,
            (SELECT COALESCE(SUM(amount), 0) FROM payment_ledger WHERE order_id = o.id AND type IN ('Deposit', 'Final', 'Installment')) as total_paid,
            (SELECT COALESCE(SUM(amount), 0) FROM payment_ledger WHERE order_id = o.id AND type = 'Refund') as total_refunded
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        WHERE o.company_id = ? AND (o.location_id = ? OR ? = 0)
        ORDER BY o.created_at DESC
    ''', (company_id, location_id, location_id))
    orders = cursor.fetchall()
    
    # Process calculated balances before rendering
    processed_orders = []
    for order in orders:
        order_dict = dict(order)
        balance_due = order_dict['total'] - (order_dict['total_paid'] - order_dict['total_refunded'])
        order_dict['balance_due'] = max(0, balance_due)
        processed_orders.append(order_dict)
        
    return render_template('orders.html', orders=processed_orders)

@bp.route('/<int:id>')
def order_detail(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get the order and customer
    cursor.execute('''
        SELECT o.*, c.first_name, c.last_name, c.email, c.phone
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        WHERE o.id = ?
    ''', (id,))
    order = cursor.fetchone()
    
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for('orders.order_list'))
        
    # Get line items
    cursor.execute('''
        SELECT oi.*, p.name as product_name, pv.size, pv.color
        FROM order_items oi
        LEFT JOIN product_variants pv ON oi.product_variant_id = pv.id
        LEFT JOIN products p ON pv.product_id = p.id
        WHERE oi.order_id = ?
    ''', (id,))
    items = cursor.fetchall()
    
    # Get the append-only ledger history
    cursor.execute('''
        SELECT pl.*, u.first_name as staff_name
        FROM payment_ledger pl
        LEFT JOIN users u ON pl.created_by = u.id
        WHERE pl.order_id = ?
        ORDER BY pl.occurred_at DESC
    ''', (id,))
    ledger = cursor.fetchall()
    
    # Calculate balance
    total_paid = sum(l['amount'] for l in ledger if l['type'] in ('Deposit', 'Final', 'Installment'))
    total_refunded = sum(l['amount'] for l in ledger if l['type'] == 'Refund')
    balance_due = max(0, order['total'] - (total_paid - total_refunded))
    
    return render_template('order_detail.html', 
                          order=order, 
                          items=items, 
                          ledger=ledger, 
                          balance_due=balance_due,
                          total_paid=total_paid)

@bp.route('/<int:id>/payment', methods=['POST'])
def post_payment(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    amount = float(request.form.get('amount', 0))
    payment_type = request.form.get('payment_type', 'Deposit')
    method = request.form.get('method', 'Card')
    reference = request.form.get('reference', '')
    memo = request.form.get('memo', '')
    
    if amount <= 0:
        flash("Payment amount must be greater than zero.", "error")
        return redirect(url_for('orders.order_detail', id=id))
        
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify order exists
    cursor.execute('SELECT customer_id FROM orders WHERE id = ?', (id,))
    order = cursor.fetchone()
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for('orders.order_list'))
        
    # Generate an immutable hash combining the vital fields
    raw_hash_string = f"{id}-{payment_type}-{amount}-{method}-{reference}-{session.get('user_id')}"
    immutable_hash = hashlib.sha256(raw_hash_string.encode()).hexdigest()
    
    try:
        # Immutable append operation to the ledger
        cursor.execute('''
            INSERT INTO payment_ledger 
            (order_id, customer_id, type, amount, method, reference, memo, created_by, immutable_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (id, order['customer_id'], payment_type, amount, method, reference, memo, session.get('user_id'), immutable_hash))
        
        conn.commit()
        flash(f"Successfully posted ${amount:.2f} {payment_type} via {method}.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Failed to post payment: {str(e)}", "error")
    finally:
        pass
        
    return redirect(url_for('orders.order_detail', id=id))
