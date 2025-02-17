from flask import Flask
from flask_migrate import Migrate
# from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from config import Config
db=SQLAlchemy()
migrate=Migrate()

def create_app():
    app=Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app,db)
    
    with app.app_context():
        from app import routes,models
        db.create_all()
    return app
