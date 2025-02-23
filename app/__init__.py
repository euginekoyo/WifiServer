from flask import Flask
from flask_migrate import Migrate
# from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from config import Config
from flask_cors import CORS
db=SQLAlchemy()
migrate=Migrate()

def create_app():
    app=Flask(__name__)
    CORS(app)
    app.config.from_object(Config)
    CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)
    db.init_app(app)
    migrate.init_app(app,db)
    
    with app.app_context():
        from app import routes,models
        db.create_all()
    return app
