from flask import request, jsonify, current_app as app
from app import db
from app.models import Package,User
import os
from twilio.rest import Client

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
VERIFY_SID = os.getenv("TWILIO_SERVICE_SID")  # Replace with your Verify Service SID


# Twilio Client
client = Client(ACCOUNT_SID, AUTH_TOKEN)


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
        User.query.filter_by(phone=phone).delete()
        new_user=User(phone=phone)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({
            "message": "OTP sent successfully",
            "status": verification.status
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/otp/verify", methods=["POST"])
def verify_otp():
    """Verifies the OTP entered by the user."""
    data = request.json
    phone = data.get("phone")
    otp_code = data.get("otp_code")

    if not phone or not otp_code:
        return jsonify({"error": "Phone number and OTP code are required"}), 400

    try:
        verification_check = client.verify.v2.services(VERIFY_SID) \
            .verification_checks.create(to=phone, code=otp_code)

        if verification_check.status == "approved":
            return jsonify({"message": "OTP verified successfully"}), 200
        else:
            return jsonify({"error": "Invalid OTP"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/package", methods=['POST'])
def addPackages():
    data=request.get_json()
    time=data.get("time")
    description=data.get("description")
    price=data.get("price")
    status=data.get("status")
     
    if not price or not description or not price or not status:
        return jsonify({"error":"Enter all details of the package"}) ,400
    
    Package.query.filter_by(time=time).delete()
    
    new_package=Package(time=time,description=description,price=price,status=status)
    db.session.add(new_package)
    db.session.commit()
    
    return jsonify({"Message":"successfully added packege{new_packages}"}),200

@app.route("/packages",methods=["GET"])
def getPackages():
    packages=Package.query.all()
    return jsonify([pkgs.to_dict() for pkgs in packages]),200

# @app.route("/getPackageID/<int:id>",methods=["GET"])
# def getPackageID(id):
#     package=Package.query.get(id)
#     if not package:
#         return jsonify({"error":"Package not found"}),400
#     return jsonify(package.to_dict()),200