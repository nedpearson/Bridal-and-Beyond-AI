from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db

bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@bp.route('/')
def catalog():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    cursor.execute('''
        SELECT p.*, v.name as vendor_name,
            (SELECT SUM(on_hand_qty) FROM product_variants WHERE product_id = p.id) as total_qty
        FROM products p
        LEFT JOIN vendors v ON p.vendor_id = v.id
        WHERE v.company_id = ?
        ORDER BY p.name ASC
    ''', (company_id,))
    products = cursor.fetchall()
    
    return render_template('inventory.html', products=products)

@bp.route('/product/<int:id>/reserve', methods=['POST'])
def reserve_product(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # In a full POS, this would capture dates and specific variants
    # For Phase 4, we generate a mock reservation to prove the flow
    qty = int(request.form.get('qty', 1))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Reserve against the first available variant for the demo
        cursor.execute('SELECT id FROM product_variants WHERE product_id = ? LIMIT 1', (id,))
        variant = cursor.fetchone()
        
        if variant:
            cursor.execute('''
                INSERT INTO reservations (product_variant_id, quantity, status)
                VALUES (?, ?, 'Reserved')
            ''', (variant['id'], qty))
            conn.commit()
            flash(f"Successfully reserved {qty} item(s).", "success")
        else:
            flash("No variants available to reserve.", "error")
            
    except Exception as e:
        conn.rollback()
        flash(f"Reservation failed: {str(e)}", "error")
    finally:
        pass
        
    return redirect(url_for('inventory.catalog'))
