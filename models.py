from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='member', nullable=False)  # 'member' or 'admin'
    joined_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    # A user has one membership (1-to-1)
    membership = db.relationship('Membership', backref='user', uselist=False, cascade='all, delete-orphan')
    # A user can log many workouts (1-to-many)
    workouts = db.relationship('Workout', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'joined_date': self.joined_date.strftime('%Y-%m-%d'),
            'membership': self.membership.to_dict() if self.membership else None
        }

class Membership(db.Model):
    __tablename__ = 'memberships'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    plan_name = db.Column(db.String(50), nullable=False)  # e.g., "Monthly Pass", "VIP Yearly"
    status = db.Column(db.String(20), default='Active', nullable=False)  # "Active", "Expired", "Cancelled"
    price = db.Column(db.Numeric(10, 2), nullable=False)
    start_date = db.Column(db.Date, default=date.today, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'plan_name': self.plan_name,
            'status': self.status,
            'price': float(self.price),
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d')
        }

class Workout(db.Model):
    __tablename__ = 'workouts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    exercise_name = db.Column(db.String(100), nullable=False)
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight_lbs = db.Column(db.Numeric(6, 2), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'exercise_name': self.exercise_name,
            'sets': self.sets,
            'reps': self.reps,
            'weight_lbs': float(self.weight_lbs),
            'date': self.date.strftime('%Y-%m-%d')
        }
