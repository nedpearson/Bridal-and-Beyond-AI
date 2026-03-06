from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db

bp = Blueprint('appointments', __name__, url_prefix='/appointments')

@bp.route('/')
def appointment_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    cursor.execute('''
        SELECT a.*, c.first_name, c.last_name, s.name as service_name, u.first_name as staff_name
        FROM appointments a
        JOIN customers c ON a.customer_id = c.id
        JOIN services s ON a.service_id = s.id
        LEFT JOIN users u ON a.assigned_staff_id = u.id
        WHERE c.company_id = ?
        ORDER BY a.start_at ASC
    ''', (company_id,))
    appointments = cursor.fetchall()
    
    return render_template('appointments.html', appointments=appointments)
