import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from dotenv import load_dotenv

# Φόρτωση των μεταβλητών από το αρχείο .env στη μνήμη του συστήματος
load_dotenv()

app = Flask(__name__)

# Ανάκτηση του μυστικού κλειδιού από το περιβάλλον
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback_key_mono_gia_development')

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Ρυθμίσεις Ασφαλείας Session Cookies
app.config['SESSION_COOKIE_SECURE'] = True     # Ενεργοποίησέ το αν έχεις HTTPS (στην παραγωγή)
app.config['SESSION_COOKIE_HTTPONLY'] = True   # Αποτρέπει την πρόσβαση στο cookie μέσω JavaScript
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Προστατεύει από ορισμένες επιθέσεις CSRF

# --- ΡΥΘΜΙΣΗ FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        # Προσοχή: Χρησιμοποιούμε "id" και "Username" όπως είναι στη βάση
        cursor.execute('SELECT id, Username FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return User(row[0], row[1])
    return None


# --- ROUTES ΕΠΙΣΚΕΠΤΩΝ ---

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/company')
def company():
    return render_template('company.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/quote/<service>')
def get_quote(service):
    return render_template('quote_form.html', service=service)


@app.route('/sendData', methods=['POST'])
def send_data():
    name = request.form.get('Name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    service = request.form.get('service_interest', 'Γενική Επικοινωνία')
    comments = request.form.get('comments')

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO leads (name, email, phone, service, message) VALUES (?, ?, ?, ?, ?)',
                       (name, email, phone, service, comments))
        conn.commit()
    return render_template('success.html', name=name, email=email)


# --- ROUTES ΔΙΑΧΕΙΡΙΣΗΣ (ADMIN) ---

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute") # Επιτρέπει 5 προσπάθειες ανά λεπτό
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username_input = request.form.get('username')
        password_input = request.form.get('password')

        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            # Αναζήτηση με βάση το Username
            cursor.execute('SELECT id, Username, password FROM users WHERE Username = ?', (username_input,))
            user_data = cursor.fetchone()

        if user_data and check_password_hash(user_data[2], password_input):
            user = User(user_data[0], user_data[1])
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Λανθασμένο όνομα χρήστη ή κωδικός.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_dashboard():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, email, phone, service, message, notes, timestamp FROM leads ORDER BY timestamp DESC')
        rows = cursor.fetchall()
    return render_template('admin.html', leads=rows)


@app.route('/admin/delete/<int:id>')
@login_required
def delete_lead(id):
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM leads WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_lead(id):
    if request.method == 'POST':
        new_entry = request.form.get('new_note', '')
        current_notes = request.form.get('old_notes', '')

        if new_entry.strip():
            with sqlite3.connect('database.db') as conn:
                timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
                updated_notes = f"[{timestamp}]: {new_entry}\n{current_notes}"
                cursor = conn.cursor()
                cursor.execute('UPDATE leads SET notes = ? WHERE id = ?', (updated_notes, id))
                conn.commit()
        return redirect(url_for('admin_dashboard'))

    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, phone, service, message, notes, timestamp FROM leads WHERE id = ?',
                       (id,))
        lead = cursor.fetchone()

    if lead:
        return render_template('edit_lead.html', lead=lead)
    return "Ο πελάτης δεν βρέθηκε", 404


if __name__ == '__main__':
    app.run(debug=True)