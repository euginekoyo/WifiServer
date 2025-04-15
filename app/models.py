from app import db
from datetime import datetime

class Package(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(100), nullable=True, server_default="Unlimited")
    price = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'time': self.time,
            'description': self.description,
            'price': self.price,
            'status': self.status
        }

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(100), nullable=False, unique=True)
    role = db.Column(db.String(100), nullable=False, server_default="user")

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "role": self.role
        }
 
class Click(db.Model):
    __tablename__ = 'click'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    data = db.Column(db.Text, nullable=True)
    timestamps = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "data": self.data,
            "timestamps": self.timestamps,
            "user_id": self.user_id
        }

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'), nullable=False)
    amount_kes = db.Column(db.Float, nullable=False)
    amount_usd = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # 'success', 'failed', 'pending'
    payment_intent_id = db.Column(db.String(100), unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'package_id': self.package_id,
            'amount_kes': self.amount_kes,
            'amount_usd': self.amount_usd,
            'status': self.status,
            'payment_intent_id': self.payment_intent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at.isoformat()
        }