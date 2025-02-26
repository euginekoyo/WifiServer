from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from config import Config
from flask_cors import CORS
from flask_jwt_extended import JWTManager  # Add this import

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()  # Create the JWTManager instance

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object(Config)
    CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)  # Initialize JWTManager with your app
    
    with app.app_context():
        from app import routes, models
        db.create_all()
    return app