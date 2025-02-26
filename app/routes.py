from flask import request, jsonify, current_app as app
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request, create_access_token
from app import db
from app.models import Package, User
import os
from twilio.rest import Client
from functools import wraps

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
VERIFY_SID = os.getenv("TWILIO_SERVICE_SID")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Custom decorators for role-based access control
def admin_required():
    """
    Custom decorator to verify the JWT and check if the user has admin role
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or user.role != "admin":
                return jsonify({"error": "Admin privileges required"}), 403
            
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def role_required(roles):
    """
    Custom decorator to verify the JWT and check if the user has one of the required roles
    roles: List of allowed roles
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or user.role not in roles:
                return jsonify({"error": f"Required role not found. Allowed roles: {', '.join(roles)}"}), 403
            
            return fn(*args, **kwargs)
        return decorator
    return wrapper

@app.route("/otp/send", methods=["POST"])
def send_otp():
    """Sends an OTP to the provided phone number."""
    data = request.get_json(silent=True)
    phone = data.get("phone")

    if not phone:
        return jsonify({"error": "Phone number is required"}), 400

    try:
        verification = client.verify.v2.services(VERIFY_SID) \
            .verifications.create(to=phone, channel="sms")
        
        # Don't delete existing user - just create if doesn't exist
        user = User.query.filter_by(phone=phone).first()
        if not user:
            new_user = User(phone=phone)
            db.session.add(new_user)
            db.session.commit()
            
        return jsonify({
            "message": "OTP sent successfully",
            "status": verification.status
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    phone = data.get("phone")
    if not phone:
        return jsonify({"error": "Phone number is required"}), 400
    
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    access_token = create_access_token(identity=user.id)  # Create JWT token
    return jsonify({
        "message": "Login successful", 
        "token": access_token,
        "role": user.role
    }), 200

@app.route("/otp/verify", methods=["POST"])
def verify_otp():
    """Verifies the OTP entered by the user."""
    data = request.json
    phone = data.get("phone")
    otp_code = data.get("otp_code")
    role = data.get("role", "user")  # Default to user if not specified

    if not phone or not otp_code:
        return jsonify({"error": "Phone number and OTP code are required"}), 400

    try:
        verification_check = client.verify.v2.services(VERIFY_SID) \
            .verification_checks.create(to=phone, code=otp_code)

        if verification_check.status == "approved":
            user = User.query.filter_by(phone=phone).first()
            if not user:
                # Only allow 'admin' role if verified by an existing admin
                if role == "admin":
                    try:
                        # Check if there are any admins yet - if not, allow first admin
                        admin_exists = User.query.filter_by(role="admin").first()
                        if not admin_exists:
                            # First user can be admin
                            pass
                        else:
                            # Try to verify admin authorization
                            jwt_header = request.headers.get('Authorization')
                            if jwt_header:
                                verify_jwt_in_request()
                                admin_id = get_jwt_identity()
                                admin_user = User.query.get(admin_id)
                                if not admin_user or admin_user.role != "admin":
                                    role = "user"  # Not authorized to create admin
                            else:
                                role = "user"  # No JWT token, not authorized
                    except:
                        # Any error means we default to user role
                        role = "user"
                
                new_user = User(phone=phone, role=role)
                db.session.add(new_user)
                db.session.commit()
                user = new_user
            
            # Create access token with user ID
            access_token = create_access_token(identity=user.id)
            
            return jsonify({
                "message": "OTP verified successfully",
                "token": access_token,
                "role": user.role
            }), 200
        else:
            return jsonify({"error": "Invalid OTP"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/package", methods=['POST'])
@admin_required()  # Only admins can add packages
def addPackages():
    data = request.get_json()
    time = data.get("time")
    description = data.get("description")
    price = data.get("price")
    status = data.get("status")

    if not time or not price or not description or not status:
        return jsonify({"error": "Enter all details of the package"}), 400

    Package.query.filter_by(time=time).delete()

    new_package = Package(time=time, description=description, price=price, status=status)
    db.session.add(new_package)
    db.session.commit()

    return jsonify({"message": "Successfully added package"}), 200

@app.route("/packages", methods=["GET"])
# @jwt_required()  # Any authenticated user can view packages
def getPackages():
    packages = Package.query.all()
    return jsonify([pkgs.to_dict() for pkgs in packages]), 200

@app.route("/getUser", methods=['GET'])
@admin_required()  # Only admins can view all users
def getUser():
    users = User.query.all()
    return jsonify([usr.to_dict() for usr in users]), 200

@app.route("/user/me", methods=["GET"])
@jwt_required()
def get_logged_in_user():
    """Fetches the details of the logged-in user from the database."""
    user_id = get_jwt_identity() # Extract user ID from the JWT token
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user.to_dict()), 200

# New routes for role management

@app.route("/user/<int:user_id>/change-role", methods=["PUT"])
@admin_required()  # Only admins can change roles
def change_role(user_id):
    """Change a user's role (admin only)"""
    data = request.get_json()
    new_role = data.get("role")
    
    if not new_role:
        return jsonify({"error": "Role is required"}), 400
        
    if new_role not in ["admin", "user"]:
        return jsonify({"error": "Invalid role. Must be 'admin' or 'user'"}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    user.role = new_role
    db.session.commit()
    
    return jsonify({
        "message": f"User role updated successfully",
        "user": user.to_dict()
    }), 200

@app.route("/admin/dashboard", methods=["GET"])
@admin_required()
def admin_dashboard():
    """Admin-only dashboard data"""
    # Get counts for admin dashboard
    user_count = User.query.filter_by(role="user").count()
    admin_count = User.query.filter_by(role="admin").count()
    package_count = Package.query.count()
    
    return jsonify({
        "user_count": user_count,
        "admin_count": admin_count,
        "package_count": package_count,
        "packages": [pkg.to_dict() for pkg in Package.query.all()]
    }), 200

@app.route("/user/dashboard", methods=["GET"])
@role_required(["user", "admin"])  # Both users and admins can access
def user_dashboard():
    """User dashboard data"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # Get appropriate data for user dashboard
    packages = Package.query.filter_by(status="Active").all()
    
    return jsonify({
        "user": user.to_dict(),
        "available_packages": [pkg.to_dict() for pkg in packages]
    }), 200