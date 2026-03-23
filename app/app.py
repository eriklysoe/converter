import os
import logging
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .routes import main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    max_mb = int(os.environ.get("MAX_FILE_SIZE", 50))
    app.config["MAX_CONTENT_LENGTH"] = max_mb * 1024 * 1024
    app.config["TEMP_DIR"] = os.environ.get("TEMP_DIR", "/config/temp")
    app.config["SECRET_KEY"] = os.urandom(24)

    os.makedirs(app.config["TEMP_DIR"], exist_ok=True)

    # Trust X-Forwarded-* headers from reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    BASE_URL = os.environ.get("BASE_URL", "http://localhost:7391").rstrip("/")
    app.config["BASE_URL"] = BASE_URL

    app.register_blueprint(main)
    return app


if __name__ == "__main__":
    if not os.environ.get("ADMIN_USER") or not os.environ.get("ADMIN_PASS"):
        raise SystemExit("ADMIN_USER and ADMIN_PASS environment variables are required.")
    app = create_app()
    app.run(host="0.0.0.0", port=7391, debug=False)
