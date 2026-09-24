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

    trusted_proxies = app.config.get("TRUSTED_PROXY_COUNT", 0)
    if trusted_proxies > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxies,
            x_proto=trusted_proxies,
            x_host=trusted_proxies,
            x_prefix=trusted_proxies,
        )

    return app