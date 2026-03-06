from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from datetime import datetime

bp = Blueprint('pickups', __name__, url_prefix='/pickups')

@bp.route('/')
def pickup_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    
    # Get all pickups with order and customer info
    cursor.execute('''
        SELECT p.*, o.id as order_ref, c.first_name, c.last_name
        FROM pickups p
        JOIN orders o ON p.order_id = o.id
        JOIN customers c ON p.customer_id = c.id
        WHERE p.company_id = ?
        ORDER BY p.scheduled_at ASC
    ''', (company_id,))
    pickups = cursor.fetchall()
    
    # Calculate simple metrics
    today_count = sum(1 for p in pickups if p['status'] != 'Completed' and getattr(p, 'scheduled_at', '') and p['scheduled_at'].startswith(datetime.now().strftime('%Y-%m-%d')))
    pending_count = sum(1 for p in pickups if p['status'] in ('Scheduled', 'Ready'))
    
    return render_template('pickups.html', pickups=pickups, today_count=today_count, pending_count=pending_count)

@bp.route('/<int:id>/complete', methods=['POST'])
def complete_pickup(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Update the pickup status, simulating a signed/completed action
        cursor.execute('''
            UPDATE pickups 
            SET status = 'Completed',
                signature_data = 'digital_signature_mock_hash'
            WHERE id = ? AND status != 'Completed'
        ''', (id,))
        
        # In a real app, we might also update the parent Order status to 'Fulfilled' here
        # depending on if all child pickups are complete
        
        conn.commit()
        flash("Pickup successfully marked as completed.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error completing pickup: {str(e)}", "error")
    finally:
        pass
        
    return redirect(url_for('pickups.pickup_list'))
