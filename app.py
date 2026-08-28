import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nhitm-complaint-portal-key-2026")

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'instance', 'complaints.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=True)
    role = db.Column(db.String(20), default='student')
    complaints = db.relationship('Complaint', backref='author', lazy=True, cascade="all, delete-orphan")

class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    image_file = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        default_admin = User(
            name="College Administration",
            username="admin",
            email="admin@nhitm.ac.in",
            password=generate_password_hash("admin123"),
            branch="Administration",
            year=None,
            role="admin"
        )
        db.session.add(default_admin)
        db.session.commit()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_panel' if session.get('role') == 'admin' else 'dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_panel' if session.get('role') == 'admin' else 'dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['name'] = user.name
            session['username'] = user.username
            session['role'] = user.role
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for('admin_panel' if user.role == 'admin' else 'dashboard'))
        else:
            flash("Invalid credentials. Please try again.", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        branch = request.form.get('branch', '').strip()
        year_str = request.form.get('year', '')
        role = request.form.get('role', 'student')

        if not email.endswith('@nhitm.ac.in'):
            flash("Registration requires an institutional email ending with @nhitm.ac.in", "warning")
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "warning")
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return render_template('register.html')

        year = int(year_str) if year_str and year_str.isdigit() else None

        user = User(
            name=name,
            username=username,
            email=email,
            password=generate_password_hash(password),
            branch=branch,
            year=year,
            role=role
        )
        db.session.add(user)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session or session.get('role') == 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'General')
        file = request.files.get('image')

        filename = None
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        complaint = Complaint(
            title=title,
            description=description,
            category=category,
            image_file=filename,
            user_id=session['user_id']
        )
        db.session.add(complaint)
        db.session.commit()
        flash("Complaint submitted successfully!", "success")
        return redirect(url_for('dashboard'))

    complaints = Complaint.query.filter_by(user_id=session['user_id']).order_by(Complaint.created_at.desc()).all()
    return render_template('dashboard.html', complaints=complaints)

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template('admin.html', complaints=complaints)

@app.route('/update_status/<int:complaint_id>', methods=['POST'])
def update_status(complaint_id):
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    complaint = Complaint.query.get_or_404(complaint_id)
    new_status = request.form.get('status')
    if new_status in ['Pending', 'In Progress', 'Resolved', 'Rejected']:
        complaint.status = new_status
        db.session.commit()
        flash(f"Status updated to {new_status}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
