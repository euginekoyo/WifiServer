# from flask import request, jsonify, current_app as app
# from app import db
# from app.models import User, OTP,Package
# from twilio.rest import Client
# from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
# from datetime import datetime, timedelta
# import os
# import random


# #
# # Twilio Configuration (from Config)
# client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

# def generate_otp():
#     """Generates a 6-digit OTP."""
#     return str(random.randint(100000, 999999))

# def send_sms(phone, otp_code):
#     """Sends OTP via Twilio."""
#     return client.messages.create(
#         body=f"Your OTP code is: {otp_code}",
#         from_=os.getenv("TWILIO_PHONE_NUMBER"),
#         to=phone
#     )

# @app.route('/send-otp', methods=['POST'])
# def send_otp():
#     """Sends an OTP to the given phone number."""
#     data = request.get_json()
#     phone = data.get("phone")

#     if not phone:
#         return jsonify({"error": "Phone number is required"}), 400

#     user = User.query.filter_by(phone=phone).first()
#     if not user:
#         user = User(phone=phone)
#         db.session.add(user)

#     # Generate OTP & Save to DB (Replaces old OTP if exists)
#     otp_code = generate_otp()
#     expires_at = datetime.utcnow() + timedelta(minutes=5)
    
#     OTP.query.filter_by(phone=phone).delete()  # Remove existing OTPs for this user
#     new_otp = OTP(phone=phone, otp_code=otp_code, expires_at=expires_at)
#     db.session.add(new_otp)
#     db.session.commit()

#     send_sms(phone, otp_code)  # Send OTP via Twilio

#     return jsonify({"message": "OTP sent successfully"}), 200

# @app.route('/verify-otp', methods=['POST'])
# def verify_otp():
#     """Verifies the OTP and authenticates the user."""
#     data = request.get_json()
#     phone, otp_code = data.get("phone"), data.get("otp")

#     if not phone or not otp_code:
#         return jsonify({"error": "Phone and OTP are required"}), 400

#     otp_entry = OTP.query.filter_by(phone=phone, otp_code=otp_code).first()

#     if not otp_entry or datetime.utcnow() > otp_entry.expires_at:
#         return jsonify({"error": "Invalid or expired OTP"}), 400

#     user = User.query.filter_by(phone=phone).first()
#     user.is_verified = True

#     db.session.delete(otp_entry)  # Remove OTP after verification
#     db.session.commit()

#     access_token = create_access_token(identity=phone)

#     return jsonify({"message": "OTP verified successfully", "token": access_token}), 200

# @app.route('/dashboard', methods=['GET'])
# @jwt_required()
# def dashboard():
#     """Protected route that requires authentication."""
#     phone = get_jwt_identity()
#     return jsonify({"message": f"Welcome to your dashboard, {phone}!"}), 200
    
    
# @app.route("/packege", methods=['POST'])
# def addPackages():
#     data=request.get_json()
#     name=data.get("name")
#     price=data.get("price")
#     status=data.get("status")
     
#     if not name or not price or not status:
#         return jsonify({"error":"Enter all details of the package"}) 
    
#     Package.query.filter_by(name=name).delete()
    
#     new_package=Package(name=name,price=price,status=status)
#     db.session.add(new_package)
#     db.session.commit()
    
#     return jsonify({"Message":"successfully added packege{new_packages}"})
    