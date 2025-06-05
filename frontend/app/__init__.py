# frontend/app/__init__.py
from flask import Flask
import sys
import os

# Configurar path para importaciones
current_dir = os.path.dirname(os.path.abspath(__file__))
service_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(service_dir)

# Agregar directorios al path
sys.path.insert(0, service_dir)
sys.path.insert(0, project_dir)

# Importaciones locales
from .routes import frontend_bp
from .services import APIClient


def create_app():
    app = Flask(__name__)

    # Cargar configuración
    try:
        # Intentar importación relativa
        from ..config import config
    except ImportError:
        # Importación absoluta si falla la relativa
        try:
            from config import config
        except ImportError:
            # Configuración por defecto si no encuentra config.py
            class DefaultConfig:
                SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-frontend'
                AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL') or 'http://localhost:5001'
                APPOINTMENT_SERVICE_URL = os.environ.get('APPOINTMENT_SERVICE_URL') or 'http://localhost:5002'
                NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL') or 'http://localhost:5003'
                MEDICAL_SERVICE_URL = os.environ.get('MEDICAL_SERVICE_URL') or 'http://localhost:5004'
                INVENTORY_SERVICE_URL = os.environ.get('INVENTORY_SERVICE_URL') or 'http://localhost:5005'
                FLASK_ENV = os.environ.get('FLASK_ENV') or 'development'
                DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']
                SESSION_TYPE = 'filesystem'
                SESSION_PERMANENT = False
                SESSION_USE_SIGNER = True
                MAX_CONTENT_LENGTH = 16 * 1024 * 1024
                UPLOAD_FOLDER = './uploads'

            config = {'development': DefaultConfig, 'default': DefaultConfig}

    env = os.environ.get('FLASK_ENV', 'development')
    config_class = config.get(env, config.get('default'))
    app.config.from_object(config_class)

    # Crear directorio de uploads si no existe
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # Inicializar el cliente API
    api_client = APIClient()
    api_client.init_app(app)

    # Hacer el cliente API disponible globalmente
    app.api_client = api_client

    # Registrar blueprints
    app.register_blueprint(frontend_bp)

    return app