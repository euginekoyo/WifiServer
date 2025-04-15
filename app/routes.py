from flask import request, jsonify, current_app as app
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request, create_access_token, unset_jwt_cookies
from app import db, jwt  # Add jwt import here
from app.models import Package, User,Click, Transaction, Notification
import os
from twilio.rest import Client
from functools import wraps
from flask_cors import cross_origin
from stripe import StripeError
import stripe
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Stripe with proper validation
stripe_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe_key or len(stripe_key) < 10:
    logger.error("Invalid or missing Stripe API key")
    raise ValueError("Stripe API key is invalid or not set")

stripe.api_key = stripe_key
logger.info(f"Stripe initialized successfully with key starting with: {stripe_key[:10]}...")

# Add these JWT error handlers before the routes
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_data):
    return jsonify({
        'status': 401,
        'sub_status': 42,
        'msg': 'The token has expired'
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({
        'status': 401,
        'sub_status': 43,
        'msg': 'Invalid token'
    }), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({
        'status': 401,
        'sub_status': 44,
        'msg': 'Missing token'
    }), 401

@app.route("/packages/<int:id>", methods=["OPTIONS"])
@cross_origin(origin="http://localhost:5173", headers=["Content-Type", "Authorization"])
def handle_preflight(id):
    """Handles the CORS preflight request for DELETE method"""
    response = jsonify({"message": "Preflight OK"})
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    return response, 200
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
        # Validate Twilio credentials
        if not all([ACCOUNT_SID, AUTH_TOKEN, VERIFY_SID]):
            logger.error("Missing Twilio credentials")
            return jsonify({"error": "Service configuration error"}), 500

        # Add logging for debugging
        logger.debug(f"Attempting to send OTP to {phone}")
        logger.debug(f"Using Verify SID: {VERIFY_SID}")

        verification = client.verify.v2.services(VERIFY_SID) \
            .verifications.create(to=phone, channel="sms")
        
        logger.info(f"Verification status: {verification.status}")
        
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
        logger.error(f"Error sending OTP: {str(e)}", exc_info=True)
        if "403" in str(e):
            return jsonify({"error": "Service authorization failed. Please contact support."}), 403
        return jsonify({"error": "Failed to send OTP. Please try again later."}), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    phone = data.get("phone")
    if not phone:
        return jsonify({"error": "Phone number is required"}), 400
    
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    access_token = create_access_token(identity=str(user.id))  # Create JWT token
    return jsonify({
        "message": "Login successful", 
        "token": access_token,
        "user":user.phone,
        "role":user.role,
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
@jwt_required() 
 # Any authenticated user can view packages
def getPackages():
    try:
        packages = Package.query.all()
        return jsonify([pkgs.to_dict() for pkgs in packages]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/package/<int:package_id>", methods=["PUT"])
@admin_required()  # Only admins can edit packages
def edit_package(package_id):
    """Edit an existing package."""
    data = request.get_json()
    package = Package.query.get(package_id)

    if not package:
        return jsonify({"error": "Package not found"}), 404

    package.time = data.get("time", package.time)
    package.description = data.get("description", package.description)
    package.price = data.get("price", package.price)
    package.status = data.get("status", package.status)

    db.session.commit()
    return jsonify({"message": "Package updated successfully", "package": package.to_dict()}), 200


@app.route("/package/<int:package_id>", methods=["DELETE"])
@admin_required()  # Only admins can delete packages
def delete_package(package_id):
    """Delete a package."""
    package = Package.query.get(package_id)

    if not package:
        return jsonify({"error": "Package not found"}), 404

    db.session.delete(package)
    db.session.commit()
    
    return jsonify({"message": "Package deleted successfully"}), 200


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
    try:
        user_count = User.query.filter_by(role="user").count()
        admin_count = User.query.filter_by(role="admin").count()
        package_count = Package.query.count()
        
        # Get today's date range
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Get transaction statistics
        successful_transactions = Transaction.query.filter_by(status='success').count()
        
        # Get total amount
        total_amount_kes = db.session.query(db.func.sum(Transaction.amount_kes))\
            .filter_by(status='success')\
            .scalar() or 0
            
        # Get today's amount
        today_amount_kes = db.session.query(db.func.sum(Transaction.amount_kes))\
            .filter(
                Transaction.status == 'success',
                Transaction.created_at >= today_start,
                Transaction.created_at < today_end
            )\
            .scalar() or 0
            
        # Get total amount including all statuses
        total_amount_kes = db.session.query(db.func.sum(Transaction.amount_kes)).scalar() or 0
        
        # Get total amount of pending transactions
        pending_amount_kes = db.session.query(db.func.sum(Transaction.amount_kes))\
            .filter_by(status='pending')\
            .scalar() or 0
            
        # Get total successful amount
        successful_amount_kes = db.session.query(db.func.sum(Transaction.amount_kes))\
            .filter_by(status='success')\
            .scalar() or 0
            
        return jsonify({
            "user_count": user_count,
            "admin_count": admin_count,
            "package_count": package_count,
            "packages": [pkg.to_dict() for pkg in Package.query.all()],
            "recent_transactions": [tx.to_dict() for tx in Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()],
            "transaction_stats": {
                "successful_count": successful_transactions,
                "total_amount_kes": float(successful_amount_kes),
                "today_amount": float(today_amount_kes),
                "pending_amount": float(pending_amount_kes),
                "total_including_pending": float(total_amount_kes)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}")
        return jsonify({"error": "Failed to fetch dashboard data"}), 500

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

@app.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Logs out the user by revoking the JWT token."""
    response = jsonify({"message": "Logout successful"})
    unset_jwt_cookies(response)  # Unset JWT cookies
    return response, 200

@app.route("/initiate-payment", methods=["POST"])
@jwt_required()  # Ensure the user is authenticated
def initiate_payment():
    """Initiates a payment using Stripe."""
    data = request.get_json()
    package_id = data.get("packageId")
    phone = data.get("phone")

    if not package_id or not phone:
        return jsonify({"error": "Package ID and phone number are required"}), 400

    package = Package.query.get(package_id)
    if not package:
        return jsonify({"error": "Package not found"}), 404

    try:
        # Create a payment intent with additional metadata
        payment_intent = stripe.PaymentIntent.create(
            amount=int(float(package.price) * 100),  # Convert price to cents
            currency="kes",
            metadata={
                "phone": phone,
                "package_id": package_id,
                "package_name": package.time,
                "user_id": get_jwt_identity()
            },
            automatic_payment_methods={"enabled": True}
        )

        return jsonify({
            "clientSecret": payment_intent.client_secret,
            "message": "Payment initiated successfully"
        }), 200

    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
        
        payment_intent = event['data']['object']
        logger.debug(f"Received webhook event: {event['type']}")
        logger.debug(f"Payment intent data: {payment_intent}")
        
        transaction = Transaction.query.filter_by(
            payment_intent_id=payment_intent.id
        ).first()
        
        if not transaction:
            logger.error(f"No transaction found for payment_intent_id: {payment_intent.id}")
            return jsonify({'error': 'Transaction not found'}), 404

        # Make sure success status is being set
        if event['type'] == 'payment_intent.succeeded':
            transaction.status = 'success'  # Ensure this is exactly 'success'
            logger.info(f"Transaction {transaction.id} marked as successful")
            db.session.commit()
            logger.debug(f"Transaction status after commit: {transaction.status}")

        if event['type'] == 'payment_intent.succeeded':
            # Payment successfully completed
            transaction.status = 'success'
            logger.info(f"Transaction {transaction.id} marked as successful")

        elif event['type'] == 'payment_intent.payment_failed':
            # Payment failed due to card decline or other issues
            transaction.status = 'failed'
            logger.info(f"Transaction {transaction.id} marked as failed")

        elif event['type'] == 'payment_intent.canceled':
            # Payment was canceled
            transaction.status = 'canceled'
            logger.info(f"Transaction {transaction.id} marked as canceled")

        elif event['type'] == 'payment_intent.processing':
            # Payment is still being processed (e.g., for bank transfers)
            transaction.status = 'processing'
            logger.info(f"Transaction {transaction.id} is processing")

        elif event['type'] == 'payment_intent.requires_action':
            # Payment needs additional action (e.g., 3D Secure)
            transaction.status = 'requires_action'
            logger.info(f"Transaction {transaction.id} requires additional action")

        elif event['type'] == 'payment_intent.requires_payment_method':
            # Previous payment attempt failed, need new payment method
            transaction.status = 'requires_payment_method'
            logger.info(f"Transaction {transaction.id} requires new payment method")

        db.session.commit()
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route("/action", methods=["POST"])
@jwt_required()  # Ensure the user is authenticated
def action():
    """Logs user actions."""
    data = request.get_json()
    data_content = data.get("data")
    action = data.get("action")
    timestamps = data.get("timestamp")  # Changed from time to timestamp
    user_id = get_jwt_identity()

    if not action or not timestamps:
        return jsonify({"error": "Action and timestamp are required"}), 400

    new_action = Click(action=action, timestamps=timestamps, data=data_content, user_id=user_id)  # Changed from time to timestamp
    db.session.add(new_action)
    db.session.commit()

    return jsonify({"message": "Action logged successfully"}), 200

@app.route("/actions", methods=["GET", "POST", "OPTIONS"])
@cross_origin(origin="http://localhost:5173", headers=["Content-Type", "Authorization"])
@jwt_required()
def handle_actions():
    """Handles both GET and POST requests for actions."""
    if request.method == "OPTIONS":
        response = jsonify({"message": "Preflight OK"})
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
        return response, 200
    
    if request.method == "GET":
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        # Admins can see all actions, users can only see their own
        if user.role == "admin":
            actions = Click.query.all()
        else:
            actions = Click.query.filter_by(user_id=user_id).all()
            
        return jsonify([action.to_dict() for action in actions]), 200
    
    # Handle POST request
    elif request.method == "POST":
        try:
            app.logger.debug(f"Received action data: {request.get_data(as_text=True)}")
            
            data = request.get_json()
            if not data:
                app.logger.error("No JSON data in request")
                return jsonify({"error": "No JSON data provided"}), 400

            app.logger.debug(f"Parsed JSON data: {data}")

            # Extract and validate fields with defaults
            data_content = data.get("data", {})
            action = data.get("action", "").strip()
            
            # Use timestamp from request or generate current timestamp
            timestamps = data.get("timestamp", "").strip()  # Changed from time to timestamp
            if not timestamps:
                from datetime import datetime
                timestamps = datetime.utcnow().isoformat()
            
            user_id = get_jwt_identity()

            # Validate action only since timestamps will always have a value
            if not action:
                app.logger.error("Missing required field: action")
                return jsonify({"error": "action field is required"}), 400

            # Create and save new action with timestamps field
            new_action = Click(
                action=action,
                timestamps=timestamps,  # Changed from time to timestamps
                data=str(data_content) if data_content else None,
                user_id=user_id
            )
            
            db.session.add(new_action)
            db.session.commit()

            response_data = {
                "message": "Action logged successfully",
                "action": new_action.to_dict()
            }
            app.logger.debug(f"Action stored successfully: {response_data}")
            return jsonify(response_data), 200

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error processing action: {str(e)}")
            return jsonify({
                "error": "Failed to process action",
                "details": str(e)
            }), 500

@app.route('/create-payment-intent', methods=['POST', 'OPTIONS'])
@cross_origin(origins=["http://localhost:5173"])  # Fix CORS warning
@jwt_required()
def create_payment_intent():
    if request.method == "OPTIONS":
        return handle_preflight()
        
    try:
        data = request.get_json()
        logger.debug(f"Received payment intent request: {data}")
        
        package_id = data.get('packageId')
        amount = data.get('amount')

        if not package_id or not amount:
            return jsonify({"error": "Package ID and amount are required"}), 400

        # Clean and validate amount
        try:
            amount_str = str(amount).replace('KES', '').strip()
            amount_float = float(amount_str)
            
            # Convert KES to USD (approximate exchange rate)
            usd_amount = amount_float * 0.0082  # Current KES to USD rate
            
            # Ensure minimum USD amount is 0.50
            min_usd = 0.50
            if usd_amount < min_usd:
                min_kes = min_usd / 0.0082
                amount_float = min_kes  # Set to minimum KES amount
                usd_amount = min_usd    # Set to minimum USD amount
            
            amount_cents = int(amount_float * 100)
            
            if amount_float <= 0:
                return jsonify({"error": "Amount must be greater than 0"}), 400
                
        except (ValueError, TypeError) as e:
            logger.error(f"Amount validation error: {str(e)}")
            return jsonify({"error": "Invalid amount format"}), 400

        logger.debug(f"Creating payment intent for amount: {amount_cents} cents (USD: ${usd_amount:.2f})")

        # Create payment intent with USD currency
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(usd_amount * 100),  # Convert to USD cents
                currency='usd',
                capture_method='automatic',
                automatic_payment_methods={
                    'enabled': True,
                    'allow_redirects': 'never'
                },
                metadata={
                    'package_id': str(package_id),
                    'user_id': str(get_jwt_identity()),
                    'original_amount_kes': str(amount_float)
                }
            )
            
            # Record the transaction
            transaction = Transaction(
                user_id=get_jwt_identity(),
                package_id=package_id,
                amount_kes=amount_float,
                amount_usd=usd_amount,
                status='pending',
                payment_intent_id=payment_intent.id
            )
            db.session.add(transaction)
            db.session.commit()
            
            logger.debug(f"Payment intent created successfully: {payment_intent.id}")
            return jsonify({
                'clientSecret': payment_intent.client_secret,
                'id': payment_intent.id,
                'amount_usd': usd_amount,
                'amount_kes': amount_float,
                'adjusted': usd_amount > float(amount) * 0.0082  # Indicate if amount was adjusted
            })

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.error(f"Unexpected error in create_payment_intent: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

# Update handle_preflight to handle all CORS headers properly
def handle_preflight():
    response = jsonify({"message": "Preflight OK"})
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.add("Access-Control-Allow-Origin", "http://localhost:5173")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response, 200

@app.route('/admin/transactions', methods=['GET'])
@admin_required()
def get_transactions():
    """Get all transactions for admin dashboard."""
    try:
        transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
        return jsonify([tx.to_dict() for tx in transactions]), 200
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        return jsonify({'error': 'Failed to fetch transactions'}), 500

def get_package_duration_timedelta(package_time):
    """Convert package time string to timedelta"""
    time_lower = package_time.lower().strip()
    number = int(''.join(filter(str.isdigit, time_lower)))
    
    if "min" in time_lower:
        return timedelta(minutes=number)
    elif "hour" in time_lower:
        return timedelta(hours=number)
    elif "day" in time_lower:
        return timedelta(days=number)
    elif "week" in time_lower:
        return timedelta(days=number * 7)
    elif "month" in time_lower:
        return timedelta(days=number * 30)
    
    # Default to minutes if no unit specified
    return timedelta(minutes=number)

@app.route("/user/purchased-packages", methods=["GET"])
@jwt_required()
def get_purchased_packages():
    try:
        user_id = get_jwt_identity()
        logger.debug(f"Fetching purchased packages for user {user_id}")
        
        current_time = datetime.now()
        transactions = Transaction.query.filter_by(user_id=user_id).all()
        
        purchased_packages = []
        for transaction in transactions:
            package = Package.query.get(transaction.package_id)
            if package:
                duration = get_package_duration_timedelta(package.time)
                expiry_date = transaction.created_at + duration
                remaining_time = expiry_date - current_time
                remaining_seconds = max(0, remaining_time.total_seconds())
                
                # Skip if no time remaining or expired
                if remaining_seconds == 0:
                    continue
                
                # Calculate time components
                remaining_days = int(remaining_seconds // 86400)
                remaining_hours = int((remaining_seconds % 86400) // 3600)
                remaining_minutes = int((remaining_seconds % 3600) // 60)
                
                # Skip if all time components are 0
                if remaining_days == 0 and remaining_hours == 0 and remaining_minutes == 0:
                    continue
                
                gradient_colors = get_gradient_colors(len(purchased_packages))
                purchased_package = package.to_dict()
                purchased_package.update({
                    'purchase_date': transaction.created_at.isoformat(),
                    'transaction_id': transaction.id,
                    'amount_paid': float(transaction.amount_kes),
                    'expiry_date': expiry_date.isoformat(),
                    'remaining_days': remaining_days,
                    'remaining_hours': remaining_hours,
                    'remaining_minutes': remaining_minutes,
                    'total_duration_seconds': duration.total_seconds(),
                    'remaining_seconds': remaining_seconds,
                    'gradientFrom': gradient_colors['from'],
                    'gradientTo': gradient_colors['to'],
                    'status': transaction.status
                })
                purchased_packages.append(purchased_package)
                
        return jsonify(purchased_packages), 200
        
    except Exception as e:
        logger.error(f"Error fetching purchased packages: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch purchased packages"}), 500

def get_gradient_colors(index):
    """Helper function to get gradient colors"""
    gradients = [
        {'from': '#3b82f6', 'to': '#8b5cf6'},
        {'from': '#ec4899', 'to': '#8b5cf6'},
        {'from': '#10b981', 'to': '#3b82f6'}
    ]
    return gradients[index % len(gradients)]

@app.route("/admin/notifications", methods=["POST"])
@admin_required()
def post_notification():
    """Admin posts a notification"""
    try:
        data = request.json
        notification = Notification(
            title=data.get("title"),
            message=data.get("message"),
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.commit()
        return jsonify({"message": "Notification posted successfully"}), 201
    except Exception as e:
        logger.error(f"Error posting notification: {str(e)}")
        return jsonify({"error": "Failed to post notification"}), 500

@app.route("/notifications", methods=["GET"])
def get_notifications():
    """Fetch notifications for clients"""
    try:
        notifications = Notification.query.order_by(Notification.created_at.desc()).all()
        return jsonify([n.to_dict() for n in notifications]), 200
    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}")
        return jsonify({"error": "Failed to fetch notifications"}), 500