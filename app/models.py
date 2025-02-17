from app import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(100), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'is_verified': self.is_verified,
            'created_at': self.created_at
        }

class OTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    expires_at = db.Column(db.DateTime, nullable=False) 

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'otp_code': self.otp_code,
            'created_at': self.created_at,
            'expires': self.expires_at
        }

class Package(db.Model):
    id=db.Column(db.Integer,primary_key=True,nullable=False)
    name=db.Column(db.String(100),nullable=False)
    status=db.Column(db.String(100),nullable=False)
    
    def to_dict(self):
        return{
        'id':self.id,
        'name':self.name,
        'status':self.status 
        }