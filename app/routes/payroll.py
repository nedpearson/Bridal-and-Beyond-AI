from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db

bp = Blueprint('payroll', __name__, url_prefix='/payroll')

@bp.route('/')
def payroll_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    location_id = session.get('location_id', 0)
    
    # Get active staff members and their pending commissions
    cursor.execute('''
        SELECT u.*, 
            COALESCE(SUM(c.amount), 0) as pending_commissions,
            (SELECT COUNT(*) FROM time_entries WHERE user_id = u.id AND approved = 0) as unapproved_timesheets
        FROM users u
        LEFT JOIN commissions c ON u.id = c.user_id AND c.status = 'Pending'
        WHERE u.active = 1 AND u.company_id = ? AND (u.location_id = ? OR ? = 0)
        GROUP BY u.id
        ORDER BY u.first_name ASC
    ''', (company_id, location_id, location_id))
    staff = cursor.fetchall()
    
    # Get recent commissions
    cursor.execute('''
        SELECT c.*, u.first_name, u.last_name, o.id as order_ref
        FROM commissions c
        JOIN users u ON c.user_id = u.id
        JOIN orders o ON c.order_id = o.id
        WHERE u.company_id = ? AND (u.location_id = ? OR ? = 0)
        ORDER BY c.earned_at DESC
        LIMIT 15
    ''', (company_id, location_id, location_id))
    commissions = cursor.fetchall()
    
    return render_template('payroll.html', staff=staff, commissions=commissions)

@bp.route('/timesheets/<int:user_id>')
def view_timesheets(user_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    person = cursor.fetchone()
    
    if not person:
        flash("Staff member not found.", "error")
        return redirect(url_for('payroll.payroll_dashboard'))
        
    cursor.execute('SELECT * FROM time_entries WHERE user_id = ? ORDER BY clock_in DESC', (user_id,))
    timesheets = cursor.fetchall()
    
    unapproved_count = sum(1 for t in timesheets if not t['approved'])
    
    return render_template('timesheets.html', person=person, timesheets=timesheets, unapproved_count=unapproved_count)

@bp.route('/timesheets/<int:user_id>/approve', methods=['POST'])
def approve_timesheets(user_id):
    if 'user_id' not in session or session.get('role') != 'Owner': 
        flash("Unauthorized to approve timesheets", "error")
        return redirect(url_for('payroll.view_timesheets', user_id=user_id))
        
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE time_entries SET approved = 1 WHERE user_id = ? AND approved = 0', (user_id,))
        conn.commit()
        flash("All pending timesheets approved.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error approving timesheets: {str(e)}", "error")
    finally:
        pass
        
    return redirect(url_for('payroll.view_timesheets', user_id=user_id))
