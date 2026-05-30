import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Membership, Workout

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gym-tracker-super-secret-key-987654'
# Place database file in the standard instance folder
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Custom decorator to check for admin access
def admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access denied. Admins only!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- AUTHENTICATION ROUTES ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.name}!', 'success')
            # Always redirect based on role — never follow ?next blindly
            # This prevents members from being sent to /admin via URL params
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        
        flash('Invalid email or password. Please try again.', 'danger')
        
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with that email already exists.', 'danger')
            return redirect(url_for('register'))
            
        # Create new user
        new_user = User(
            name=name,
            email=email,
            role='member'
        )
        new_user.set_password(password)
        
        # Automatically assign a free 30-day "Monthly Pass" trial
        trial_membership = Membership(
            plan_name='Monthly Pass',
            status='Active',
            price=Decimal('49.99'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30)
        )
        new_user.membership = trial_membership
        
        db.session.add(new_user)
        db.session.add(trial_membership)
        db.session.commit()
        
        login_user(new_user)
        flash('Account registered successfully! Welcome to Gym Tracker!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# --- MEMBER DASHBOARD & WORKOUT CRUD ---

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
        
    # Get recent workouts (ordered by date descending, then id descending)
    workouts = Workout.query.filter_by(user_id=current_user.id).order_by(Workout.date.desc(), Workout.id.desc()).all()
    
    # Calculate some helper stats for the dashboard
    total_workouts = len(workouts)
    max_weight = db.session.query(db.func.max(Workout.weight_lbs)).filter_by(user_id=current_user.id).scalar() or 0
    total_sets = db.session.query(db.func.sum(Workout.sets)).filter_by(user_id=current_user.id).scalar() or 0
    
    # Calculate days remaining for membership
    days_left = 0
    if current_user.membership and current_user.membership.status == 'Active':
        delta = current_user.membership.end_date - date.today()
        days_left = max(0, delta.days)
        
    return render_template(
        'dashboard.html', 
        workouts=workouts, 
        total_workouts=total_workouts,
        max_weight=float(max_weight),
        total_sets=total_sets,
        days_left=days_left
    )

# Get workout history in JSON format for the chart
@app.route('/api/workouts/history')
@login_required
def workout_history_api():
    # Fetch user's workouts in chronological order
    workouts = Workout.query.filter_by(user_id=current_user.id).order_by(Workout.date.asc()).all()
    # Format for JSON
    data = [w.to_dict() for w in workouts]
    return jsonify(data)

# Create Workout
@app.route('/api/workouts', methods=['POST'])
@login_required
def create_workout():
    try:
        # Handle both standard forms and AJAX JSON requests
        if request.is_json:
            data = request.get_json()
            exercise_name = data.get('exercise_name')
            sets = int(data.get('sets', 0))
            reps = int(data.get('reps', 0))
            weight_lbs = Decimal(str(data.get('weight_lbs', 0)))
            date_str = data.get('date')
        else:
            exercise_name = request.form.get('exercise_name')
            sets = int(request.form.get('sets', 0))
            reps = int(request.form.get('reps', 0))
            weight_lbs = Decimal(request.form.get('weight_lbs', 0))
            date_str = request.form.get('date')
            
        if not exercise_name or sets <= 0 or reps <= 0 or weight_lbs < 0:
            return jsonify({'success': False, 'message': 'Invalid input values. Set name, positive sets/reps.'}), 400
            
        workout_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
        
        new_workout = Workout(
            user_id=current_user.id,
            exercise_name=exercise_name.strip(),
            sets=sets,
            reps=reps,
            weight_lbs=weight_lbs,
            date=workout_date
        )
        
        db.session.add(new_workout)
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True, 'workout': new_workout.to_dict()})
            
        flash('Workout logged successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Update Workout
@app.route('/api/workouts/<int:workout_id>', methods=['PUT', 'POST'])
@login_required
def update_workout(workout_id):
    workout = Workout.query.get_or_400(workout_id)
    
    # Secure: Check if the workout belongs to the current user
    if workout.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access unauthorized.'}), 403
        
    try:
        if request.is_json:
            data = request.get_json()
            exercise_name = data.get('exercise_name')
            sets = int(data.get('sets'))
            reps = int(data.get('reps'))
            weight_lbs = Decimal(str(data.get('weight_lbs')))
            date_str = data.get('date')
        else:
            exercise_name = request.form.get('exercise_name')
            sets = int(request.form.get('sets'))
            reps = int(request.form.get('reps'))
            weight_lbs = Decimal(request.form.get('weight_lbs'))
            date_str = request.form.get('date')
            
        if not exercise_name or sets <= 0 or reps <= 0 or weight_lbs < 0:
            return jsonify({'success': False, 'message': 'Invalid input values.'}), 400
            
        workout.exercise_name = exercise_name.strip()
        workout.sets = sets
        workout.reps = reps
        workout.weight_lbs = weight_lbs
        if date_str:
            workout.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
        db.session.commit()
        
        if request.is_json or request.method == 'PUT':
            return jsonify({'success': True, 'workout': workout.to_dict()})
            
        flash('Workout updated successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Delete Workout
@app.route('/api/workouts/<int:workout_id>/delete', methods=['POST'])
@app.route('/api/workouts/<int:workout_id>', methods=['DELETE'])
@login_required
def delete_workout(workout_id):
    workout = Workout.query.get_or_400(workout_id)
    
    # Secure: Check if the workout belongs to the current user
    if workout.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access unauthorized.'}), 403
        
    try:
        db.session.delete(workout)
        db.session.commit()
        
        if request.is_json or request.method == 'DELETE':
            return jsonify({'success': True, 'message': 'Workout deleted.'})
            
        flash('Workout deleted successfully.', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- ADMIN PANEL ROUTES ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    # General metric statistics
    total_users = User.query.count()
    total_members = User.query.filter_by(role='member').count()
    active_memberships = Membership.query.filter_by(status='Active').count()
    
    # Revenue is sum of active membership plan prices
    active_prices = db.session.query(db.func.sum(Membership.price)).filter_by(status='Active').scalar() or 0
    total_revenue = float(active_prices)
    
    total_workouts = Workout.query.count()
    
    # Fetch all users with memberships
    users = User.query.order_by(User.joined_date.desc()).all()
    
    return render_template(
        'admin.html',
        total_users=total_users,
        total_members=total_members,
        active_memberships=active_memberships,
        total_revenue=total_revenue,
        total_workouts=total_workouts,
        users=users
    )

# Admin Add Member/Admin
@app.route('/admin/user/create', methods=['POST'])
@admin_required
def admin_create_user():
    name = request.form.get('name').strip()
    email = request.form.get('email').strip().lower()
    password = request.form.get('password')
    role = request.form.get('role', 'member')
    
    # Membership plan info (for member accounts)
    plan_name = request.form.get('plan_name', 'Monthly Pass')
    price_val = Decimal(request.form.get('price', '49.99'))
    duration_days = int(request.form.get('duration_days', '30'))
    
    if not name or not email or not password:
        flash('Name, email, and password are required!', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    # Check duplicate email
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('A user with that email already exists.', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    try:
        new_user = User(
            name=name,
            email=email,
            role=role
        )
        new_user.set_password(password)
        db.session.add(new_user)
        
        # If member, add membership
        if role == 'member':
            membership = Membership(
                plan_name=plan_name,
                status='Active',
                price=price_val,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=duration_days)
            )
            new_user.membership = membership
            db.session.add(membership)
            
        db.session.commit()
        flash(f'User "{name}" created successfully as a {role}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating user: {str(e)}', 'danger')
        
    return redirect(url_for('admin_dashboard'))

# Admin Update Membership
@app.route('/admin/membership/<int:membership_id>/update', methods=['POST'])
@admin_required
def admin_update_membership(membership_id):
    membership = Membership.query.get_or_400(membership_id)
    
    plan_name = request.form.get('plan_name')
    status = request.form.get('status')
    price_val = Decimal(request.form.get('price', '49.99'))
    duration_days = int(request.form.get('duration_days', '30'))
    
    try:
        membership.plan_name = plan_name
        membership.status = status
        membership.price = price_val
        
        # Adjust end date based on status updates
        if status == 'Active':
            # Renew/extend
            membership.start_date = date.today()
            membership.end_date = date.today() + timedelta(days=duration_days)
        elif status == 'Cancelled' or status == 'Expired':
            # Keep dates but set status
            pass
            
        db.session.commit()
        flash(f'Membership for {membership.user.name} updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating membership: {str(e)}', 'danger')
        
    return redirect(url_for('admin_dashboard'))

# Admin Delete User
@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    user = User.query.get_or_400(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'User "{user.name}" has been permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
        
    return redirect(url_for('admin_dashboard'))


# --- DATABASE INITIALIZATION & RUN ---

def seed_database():
    # Only seed if users table is empty
    if User.query.first() is None:
        print("Seeding initial database content...")
        # 1. Create Default Admin
        admin = User(
            name="Admin Manager",
            email="admin@gymtracker.com",
            role="admin"
        )
        admin.set_password("adminpass")
        db.session.add(admin)
        
        # 2. Create Default Member
        jane = User(
            name="Jane Doe",
            email="jane@gymtracker.com",
            role="member"
        )
        jane.set_password("memberpass")
        
        # Give Jane an active "VIP Yearly" pass
        jane_membership = Membership(
            plan_name="VIP Yearly",
            status="Active",
            price=Decimal("499.99"),
            start_date=date.today() - timedelta(days=60),  # Joined 60 days ago
            end_date=date.today() + timedelta(days=305)   # 305 days remaining
        )
        jane.membership = jane_membership
        db.session.add(jane)
        db.session.add(jane_membership)
        
        # 3. Add seed workouts for Jane (so charts look amazing out-of-the-box!)
        workouts = [
            Workout(user=jane, exercise_name="Squat", sets=3, reps=10, weight_lbs=Decimal("135.0"), date=date.today() - timedelta(days=12)),
            Workout(user=jane, exercise_name="Bench Press", sets=4, reps=8, weight_lbs=Decimal("95.0"), date=date.today() - timedelta(days=10)),
            Workout(user=jane, exercise_name="Deadlift", sets=1, reps=5, weight_lbs=Decimal("185.0"), date=date.today() - timedelta(days=8)),
            Workout(user=jane, exercise_name="Squat", sets=4, reps=8, weight_lbs=Decimal("145.0"), date=date.today() - timedelta(days=5)),
            Workout(user=jane, exercise_name="Bench Press", sets=3, reps=8, weight_lbs=Decimal("105.0"), date=date.today() - timedelta(days=3)),
            Workout(user=jane, exercise_name="Overhead Press", sets=3, reps=10, weight_lbs=Decimal("65.0"), date=date.today() - timedelta(days=1)),
        ]
        for w in workouts:
            db.session.add(w)
            
        db.session.commit()
        print("Database seeded successfully!")

# Ensure app instance folder exists
os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

with app.app_context():
    db.create_all()
    seed_database()

if __name__ == '__main__':
    app.run(debug=True)
