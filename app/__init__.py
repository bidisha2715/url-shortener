from flask import Flask

from .config import Config
from . import db

def create_app():
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static'
    )
    app.config.from_object(Config)
    db.init_app(app)

    from .auth import auth
    from .urls import urls
    app.register_blueprint(auth)
    app.register_blueprint(urls)

    return app