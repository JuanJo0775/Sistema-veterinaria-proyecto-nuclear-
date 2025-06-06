# microservices/auth_service/main.py
import os
import sys

# Agregar el directorio actual y padre al path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

# Ahora importar el módulo app
try:
    from app import create_app
except ImportError:
    # Si falla, intentar con la estructura de paquetes
    import app
    from app import create_app

# Importar utilidades
try:
    from utils import create_health_endpoint, setup_logger
except ImportError:
    # Si no encuentra utils, crear funciones básicas
    import logging
    import time
    from datetime import datetime
    from flask import jsonify


    def setup_logger(name, level=logging.INFO):
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        return logger


    def create_health_endpoint(app, service_name, db=None):
        @app.route('/health', methods=['GET'])
        def health_check():
            health_data = {
                'service': service_name,
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat()
            }

            # Check database connection if provided
            if db:
                try:
                    db.session.execute('SELECT 1')
                    health_data['database'] = 'connected'
                except Exception as e:
                    health_data['database'] = 'disconnected'
                    health_data['database_error'] = str(e)
                    health_data['status'] = 'unhealthy'

            status_code = 200 if health_data['status'] == 'healthy' else 503
            return jsonify(health_data), status_code


def fix_password_hashes(app, db):
    """Arreglar todos los hashes de contraseñas en la base de datos"""
    try:
        with app.app_context():
            from app.models.user import User
            from werkzeug.security import generate_password_hash, check_password_hash

            print("🔧 Verificando y arreglando hashes de contraseñas...")

            # Obtener todos los usuarios
            users = User.query.all()
            fixed_count = 0

            # Definir contraseñas por defecto para usuarios conocidos
            default_passwords = {
                'admin@veterinariaclinic.com': 'admin123',
                'vet@veterinariaclinic.com': 'vet123',
                'recepcion@veterinariaclinic.com': 'recep123',
                'cliente@example.com': 'cliente123'
            }

            for user in users:
                try:
                    # Si es un usuario conocido y tiene problemas con el hash
                    if user.email in default_passwords:
                        password = default_passwords[user.email]

                        # Verificar si el hash actual funciona
                        try:
                            if not check_password_hash(user.password_hash, password):
                                raise ValueError("Hash no funciona")
                        except:
                            # El hash no funciona, necesita ser arreglado
                            print(f"🔧 Arreglando hash para: {user.email}")

                            # Generar nuevo hash compatible
                            new_hash = generate_password_hash(password, method='pbkdf2:sha256')
                            user.password_hash = new_hash
                            fixed_count += 1

                            # Verificar que el nuevo hash funciona
                            if check_password_hash(new_hash, password):
                                print(f"✅ Hash arreglado para: {user.email}")
                            else:
                                print(f"❌ Error arreglando hash para: {user.email}")

                except Exception as e:
                    print(f"⚠️ Error procesando usuario {user.email}: {e}")
                    continue

            if fixed_count > 0:
                db.session.commit()
                print(f"✅ {fixed_count} hashes de contraseñas arreglados")
            else:
                print("ℹ️ Todos los hashes están funcionando correctamente")

            return True

    except Exception as e:
        print(f"❌ Error arreglando hashes: {e}")
        return False


def create_admin_user_if_not_exists(app, db):
    """Crear usuario administrador si no existe"""
    try:
        with app.app_context():
            from app.models.user import User
            from werkzeug.security import generate_password_hash

            # Verificar si ya existe un administrador
            admin_exists = User.query.filter_by(email='admin@veterinariaclinic.com').first()

            if admin_exists:
                print("ℹ️ Usuario administrador ya existe")
                return True

            print("🔐 Creando usuario administrador por defecto...")

            # Crear usuario administrador con hash correcto
            admin_user = User(
                email='admin@veterinariaclinic.com',
                first_name='Administrador',
                last_name='Sistema',
                phone='+1234567890',
                role='admin'
            )

            # Generar hash usando método específico para compatibilidad
            password_hash = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin_user.password_hash = password_hash

            db.session.add(admin_user)
            db.session.commit()

            print("✅ Usuario administrador creado exitosamente!")
            print("📧 Email: admin@veterinariaclinic.com")
            print("🔑 Contraseña: admin123")

            return True

    except Exception as e:
        print(f"❌ Error creando usuario administrador: {e}")
        return False


def create_sample_users_if_needed(app, db):
    """Crear usuarios de ejemplo si no existen"""
    try:
        with app.app_context():
            from app.models.user import User
            from werkzeug.security import generate_password_hash

            # Lista de usuarios de ejemplo
            sample_users = [
                {
                    'email': 'vet@veterinariaclinic.com',
                    'password': 'vet123',
                    'first_name': 'Dr. Juan',
                    'last_name': 'Pérez',
                    'phone': '+1234567891',
                    'role': 'veterinarian'
                },
                {
                    'email': 'recepcion@veterinariaclinic.com',
                    'password': 'recep123',
                    'first_name': 'María',
                    'last_name': 'García',
                    'phone': '+1234567892',
                    'role': 'receptionist'
                },
                {
                    'email': 'cliente@example.com',
                    'password': 'cliente123',
                    'first_name': 'Carlos',
                    'last_name': 'López',
                    'phone': '+1234567893',
                    'role': 'client'
                }
            ]

            users_created = 0
            for user_data in sample_users:
                # Verificar si el usuario ya existe
                existing_user = User.query.filter_by(email=user_data['email']).first()

                if not existing_user:
                    new_user = User(
                        email=user_data['email'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name'],
                        phone=user_data['phone'],
                        role=user_data['role']
                    )

                    # Generar hash con método específico
                    password_hash = generate_password_hash(user_data['password'], method='pbkdf2:sha256')
                    new_user.password_hash = password_hash

                    db.session.add(new_user)
                    users_created += 1
                    print(f"👤 Usuario {user_data['role']} creado: {user_data['email']}")

            if users_created > 0:
                db.session.commit()
                print(f"✅ {users_created} usuarios de ejemplo creados")
            else:
                print("ℹ️ Usuarios de ejemplo ya existen")

    except Exception as e:
        print(f"⚠️ Error creando usuarios de ejemplo: {e}")


def show_werkzeug_info():
    """Mostrar información de Werkzeug para debugging"""
    try:
        import werkzeug
        print(f"📦 Werkzeug versión: {werkzeug.__version__}")

        # Test rápido de hash
        from werkzeug.security import generate_password_hash, check_password_hash
        test_password = "test123"
        test_hash = generate_password_hash(test_password, method='pbkdf2:sha256')
        test_result = check_password_hash(test_hash, test_password)
        print(f"🧪 Test de hash: {'✅ OK' if test_result else '❌ FALLO'}")

    except Exception as e:
        print(f"⚠️ Error obteniendo info de Werkzeug: {e}")


def main():
    app = create_app()

    # Configurar logging
    logger = setup_logger('auth_service')

    # Mostrar información del entorno
    show_werkzeug_info()

    # Configurar health check
    try:
        from app.models import db
        create_health_endpoint(app, 'auth_service', db)

        # 🔐 CREAR Y ARREGLAR USUARIOS AUTOMÁTICAMENTE
        print("🔄 Verificando usuario administrador...")
        create_admin_user_if_not_exists(app, db)

        # Crear usuarios de ejemplo
        create_sample_users_if_needed(app, db)

        # 🔧 ARREGLAR HASHES DE CONTRASEÑAS SI ES NECESARIO
        print("🔧 Verificando hashes de contraseñas...")
        fix_password_hashes(app, db)

    except ImportError:
        create_health_endpoint(app, 'auth_service')

    logger.info("🚀 Auth Service iniciado en puerto 5001")
    logger.info("🔐 Admin: admin@veterinariaclinic.com / admin123")


    return app


if __name__ == '__main__':
    app = main()
    app.run(host='0.0.0.0', port=5001, debug=True)