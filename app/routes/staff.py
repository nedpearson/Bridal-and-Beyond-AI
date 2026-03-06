from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db

bp = Blueprint('staff', __name__, url_prefix='/staff')

@bp.route('/')
def staff_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    
    # Get all active employees for the company, joined with location
    cursor.execute('''
        SELECT u.*, l.name as location_name 
        FROM users u
        LEFT JOIN locations l ON u.location_id = l.id
        WHERE u.company_id = ? AND u.active = 1
        ORDER BY u.first_name ASC
    ''', (company_id,))
    employees = cursor.fetchall()
    
    # We also need to send the locations for the "New Employee" dropdown
    cursor.execute("SELECT id, name FROM locations WHERE company_id = ? AND active = 1 ORDER BY name ASC", (company_id,))
    locations = cursor.fetchall()
    
    return render_template('staff.html', employees=employees, locations=locations)

@bp.route('/add', methods=['POST'])
def add_employee():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # Must be Owner or Manager to add staff (in a real app we'd have stricter decorator checks)
    if session.get('role') not in ('Owner', 'Manager'):
        flash("You do not have permission to add staff.", "error")
        return redirect(url_for('staff.staff_list'))
        
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    role = request.form.get('role', 'Stylist')
    location_id = request.form.get('location_id') # Crucial requirement
    password = request.form.get('password', 'password123') # Default for demo
    
    # Mock password hashing for demo
    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash(password)
    
    conn = get_db()
    cursor = conn.cursor()
    company_id = session.get('company_id')
    
    try:
        cursor.execute('''
            INSERT INTO users (company_id, location_id, email, password_hash, role, first_name, last_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (company_id, location_id, email, password_hash, role, first_name, last_name))
        conn.commit()
        flash(f"Successfully added {first_name} {last_name} to the team.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error adding staff member: {str(e)}", "error")
        
    return redirect(url_for('staff.staff_list'))
