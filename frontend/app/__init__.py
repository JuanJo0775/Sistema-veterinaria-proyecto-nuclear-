# frontend/app/__init__.py - VERSIÓN ARREGLADA
from flask import Flask
from flask_session import Session
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
            from datetime import timedelta

            class DefaultConfig:
                SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-frontend-super-secure-2024'
                AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL') or 'http://localhost:5001'
                APPOINTMENT_SERVICE_URL = os.environ.get('APPOINTMENT_SERVICE_URL') or 'http://localhost:5002'
                NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL') or 'http://localhost:5003'
                MEDICAL_SERVICE_URL = os.environ.get('MEDICAL_SERVICE_URL') or 'http://localhost:5004'
                INVENTORY_SERVICE_URL = os.environ.get('INVENTORY_SERVICE_URL') or 'http://localhost:5005'
                FLASK_ENV = os.environ.get('FLASK_ENV') or 'development'
                DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']

                # Session Configuration
                SESSION_TYPE = 'filesystem'
                SESSION_PERMANENT = True
                SESSION_USE_SIGNER = True
                SESSION_KEY_PREFIX = 'veterinary_frontend:'
                PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
                SESSION_COOKIE_SECURE = False
                SESSION_COOKIE_HTTPONLY = True
                SESSION_COOKIE_SAMESITE = 'Lax'

                MAX_CONTENT_LENGTH = 16 * 1024 * 1024
                UPLOAD_FOLDER = './uploads'

            config = {'development': DefaultConfig, 'default': DefaultConfig}

    env = os.environ.get('FLASK_ENV', 'development')
    config_class = config.get(env, config.get('default'))
    app.config.from_object(config_class)

    # Crear directorio de uploads si no existe
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # Crear directorio para sesiones
    session_dir = os.path.join(upload_folder, 'flask_session')
    os.makedirs(session_dir, exist_ok=True)

    # Inicializar Flask-Session
    try:
        Session(app)
        print("✅ Flask-Session inicializado correctamente")
    except Exception as e:
        print(f"⚠️ Error inicializando Flask-Session: {e}")

    # Inicializar el cliente API
    api_client = APIClient()
    api_client.init_app(app)

    # Hacer el cliente API disponible globalmente
    app.api_client = api_client

    # Registrar blueprints
    app.register_blueprint(frontend_bp)

    print(f"✅ Frontend configurado - Entorno: {env}")
    return app