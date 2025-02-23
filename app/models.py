from app import db

class Package(db.Model):
    id=db.Column(db.Integer,primary_key=True,nullable=False)
    time=db.Column(db.String(100),nullable=False)
    description=db.Column(db.String(100),nullable=True,server_default="Unlimited")
    price=db.Column(db.String(100),nullable=False)
    status=db.Column(db.String(100),nullable=False)
    
    def to_dict(self):
        return{
        'id':self.id,
        'time':self.time,
        'description':self.description,
        'price':self.price,
        'status':self.status 
        }

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True,nullable=False)
    phone=db.Column(db.String(100),nullable=False)
    role=db.Column(db.String(100),nullable=False,server_default="user")

    def to_dict(self):
        return{
            "id":self.id,
            "phone":self.phone,
            "role":self.role
        }
          