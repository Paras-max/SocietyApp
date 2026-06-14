import os
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from pyngrok import ngrok

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'society_secret_key_pro'

# Supabase PostgreSQL Connection URL
DATABASE_URL = "postgresql://postgres:1234vedant1234@db.vmbddsodiarujdylmdjr.supabase.co:5432/postgres"

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    
    # Create tables
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        flat_no TEXT
    )''')
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS residents (
        id SERIAL PRIMARY KEY,
        name TEXT,
        flat_no TEXT UNIQUE,
        phone TEXT,
        email TEXT,
        owner_or_tenant TEXT,
        members INTEGER,
        move_in_date DATE
    )''')
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS visitors (
        id SERIAL PRIMARY KEY,
        visitor_name TEXT,
        flat_no TEXT,
        purpose TEXT,
        phone TEXT,
        approved_by TEXT,
        entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        exit_time TIMESTAMP
    )''')
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS complaints (
        id SERIAL PRIMARY KEY,
        flat_no TEXT,
        subject TEXT,
        description TEXT,
        status TEXT DEFAULT 'Open',
        filed_date DATE DEFAULT CURRENT_DATE,
        resolved_date DATE
    )''')
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS notices (
        id SERIAL PRIMARY KEY,
        title TEXT,
        content TEXT,
        posted_by TEXT,
        posted_date DATE DEFAULT CURRENT_DATE
    )''')
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS staff (
        id SERIAL PRIMARY KEY,
        name TEXT,
        role TEXT,
        phone TEXT,
        salary NUMERIC,
        shift TEXT,
        join_date DATE,
        status TEXT DEFAULT 'Active'
    )''')
    
    # Check and Seed Default Users
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()['count'] == 0:
        def hash_pass(p): return hashlib.sha256(p.encode()).hexdigest()
        
        users = [
            ('admin', hash_pass('admin123'), 'Admin', 'Office'),
            ('resident', hash_pass('res123'), 'Resident', 'A-101'),
            ('security', hash_pass('sec123'), 'Security', 'Gate-1')
        ]
        
        for u in users:
            cur.execute("INSERT INTO users (username, password, role, flat_no) VALUES (%s, %s, %s, %s)", u)
            
    conn.commit()
    cur.close()
    conn.close()
    print("Database Initialized Successfully.")

# Authentication Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, hashed_pw))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['flat_no'] = user['flat_no']
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Stats
    cur.execute("SELECT COUNT(*) FROM residents")
    res_count = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Open'")
    comp_count = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) FROM staff WHERE status = 'Active'")
    staff_count = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) FROM visitors WHERE entry_time::date = CURRENT_DATE")
    vis_count = cur.fetchone()['count']
    
    # Recent Notices
    cur.execute("SELECT * FROM notices ORDER BY id DESC LIMIT 3")
    recent_notices = cur.fetchall()
    
    cur.close()
    conn.close()
    
    stats = {
        'residents': res_count,
        'complaints': comp_count,
        'staff': staff_count,
        'visitors': vis_count
    }
    
    current_date = datetime.now().strftime("%B %d, %Y")
    
    return render_template('dashboard.html', stats=stats, recent_notices=recent_notices, current_date=current_date)

@app.route('/residents')
@login_required
def residents():
    if session['role'] != 'Admin':
        flash("Unauthorized Access.", "danger")
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM residents ORDER BY flat_no")
    res_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('residents.html', residents=res_list)

@app.route('/residents_action', methods=['POST'])
@login_required
def residents_action():
    if session['role'] != 'Admin': return redirect(url_for('dashboard'))
    
    action = request.form.get('action')
    conn = get_db_connection()
    cur = conn.cursor()
    
    if action == 'add':
        cur.execute("INSERT INTO residents (name, flat_no, phone, email, owner_or_tenant, members, move_in_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (request.form['name'], request.form['flat_no'], request.form['phone'], request.form['email'], 
                     request.form['owner_or_tenant'], request.form['members'], request.form['move_in_date']))
        flash("Resident added successfully!", "success")
        
    elif action == 'edit':
        cur.execute("UPDATE residents SET name=%s, flat_no=%s, phone=%s, email=%s, owner_or_tenant=%s, members=%s, move_in_date=%s WHERE id=%s",
                    (request.form['name'], request.form['flat_no'], request.form['phone'], request.form['email'], 
                     request.form['owner_or_tenant'], request.form['members'], request.form['move_in_date'], request.form['id']))
        flash("Resident updated successfully!", "info")
        
    elif action == 'delete':
        cur.execute("DELETE FROM residents WHERE id=%s", (request.form['id'],))
        flash("Resident removed.", "danger")
        
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('residents'))

@app.route('/visitors')
@login_required
def visitors():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM visitors ORDER BY entry_time DESC")
    vis_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('visitors.html', visitors=vis_list)

@app.route('/visitors_action', methods=['POST'])
@login_required
def visitors_action():
    action = request.form.get('action')
    conn = get_db_connection()
    cur = conn.cursor()
    
    if action == 'add' and session['role'] == 'Security':
        cur.execute("INSERT INTO visitors (visitor_name, flat_no, purpose, phone, approved_by) VALUES (%s, %s, %s, %s, %s)",
                    (request.form['visitor_name'], request.form['flat_no'], request.form['purpose'], request.form['phone'], session['username']))
        flash("Visitor entry registered.", "success")
        
    elif action == 'exit' and session['role'] == 'Security':
        cur.execute("UPDATE visitors SET exit_time=%s WHERE id=%s", (datetime.now(), request.form['id']))
        flash("Visitor exit recorded.", "info")
        
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('visitors'))

@app.route('/complaints')
@login_required
def complaints():
    conn = get_db_connection()
    cur = conn.cursor()
    if session['role'] == 'Admin':
        cur.execute("SELECT * FROM complaints ORDER BY status DESC, filed_date DESC")
    else:
        cur.execute("SELECT * FROM complaints WHERE flat_no = %s ORDER BY filed_date DESC", (session['flat_no'],))
    
    comp_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('complaints.html', complaints=comp_list)

@app.route('/complaints_action', methods=['POST'])
@login_required
def complaints_action():
    action = request.form.get('action')
    conn = get_db_connection()
    cur = conn.cursor()
    
    if action == 'add' and session['role'] == 'Resident':
        cur.execute("INSERT INTO complaints (flat_no, subject, description) VALUES (%s, %s, %s)",
                    (session['flat_no'], request.form['subject'], request.form['description']))
        flash("Complaint submitted.", "success")
        
    elif action == 'resolve' and session['role'] == 'Admin':
        cur.execute("UPDATE complaints SET status='Resolved', resolved_date=CURRENT_DATE WHERE id=%s", (request.form['id'],))
        flash("Complaint marked as resolved.", "success")
        
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('complaints'))

@app.route('/notices')
@login_required
def notices():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM notices ORDER BY posted_date DESC")
    notice_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('notices.html', notices=notice_list)

@app.route('/notices_action', methods=['POST'])
@login_required
def notices_action():
    if session['role'] != 'Admin': return redirect(url_for('dashboard'))
    
    action = request.form.get('action')
    conn = get_db_connection()
    cur = conn.cursor()
    
    if action == 'add':
        cur.execute("INSERT INTO notices (title, content, posted_by) VALUES (%s, %s, %s)",
                    (request.form['title'], request.form['content'], session['username']))
        flash("Notice posted.", "success")
    elif action == 'delete':
        cur.execute("DELETE FROM notices WHERE id=%s", (request.form['id'],))
        flash("Notice removed.", "danger")
        
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('notices'))

@app.route('/staff')
@login_required
def staff():
    if session['role'] != 'Admin': return redirect(url_for('dashboard'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM staff ORDER BY name")
    staff_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('staff.html', staff=staff_list)

@app.route('/staff_action', methods=['POST'])
@login_required
def staff_action():
    if session['role'] != 'Admin': return redirect(url_for('dashboard'))
    
    action = request.form.get('action')
    conn = get_db_connection()
    cur = conn.cursor()
    
    if action == 'add':
        cur.execute("INSERT INTO staff (name, role, phone, salary, shift, join_date, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (request.form['name'], request.form['role'], request.form['phone'], 
                     request.form['salary'], request.form['shift'], request.form['join_date'], request.form['status']))
        flash("Staff registered.", "success")
        
    elif action == 'edit':
        cur.execute("UPDATE staff SET name=%s, role=%s, phone=%s, salary=%s, shift=%s, join_date=%s, status=%s WHERE id=%s",
                    (request.form['name'], request.form['role'], request.form['phone'], 
                     request.form['salary'], request.form['shift'], request.form['join_date'], request.form['status'], request.form['id']))
        flash("Staff details updated.", "info")
        
    elif action == 'delete':
        cur.execute("DELETE FROM staff WHERE id=%s", (request.form['id'],))
        flash("Staff removed.", "danger")
        
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('staff'))

if __name__ == '__main__':
    # Initialize DB
    init_db()
    
    # Optional ngrok configuration
    ngrok.set_auth_token("39bLvrLS0VE7GCKITuRmNA8nRI9_4WGzL6TwEEGPFdPZJBUom")
    public_url = ngrok.connect(5000).public_url
    print(f" * Public URL: {public_url}")
    print(f" * Local URL: http://localhost:5000")
    
    app.run(port=5000)
