from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from config import Config
from flask_cors import CORS
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Add Stripe configuration
    if not app.config.get('STRIPE_SECRET_KEY'):
        app.logger.error("STRIPE_SECRET_KEY not configured!")

    # Update JWT configuration
    app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = Config.JWT_ACCESS_TOKEN_EXPIRES

    # Update CORS configuration
    CORS(
        app,
        resources={
            r"/*": {
                "origins": ["http://localhost:5173"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "expose_headers": ["Content-Range", "X-Content-Range"],
                "allow_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True,
                "max_age": 120  # Cache preflight requests
            }
        }
    )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    with app.app_context():
        from app import routes, models
        db.create_all()

    return app
