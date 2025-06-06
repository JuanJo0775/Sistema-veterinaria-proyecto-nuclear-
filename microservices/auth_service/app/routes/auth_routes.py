# microservices/auth_service/app/routes/auth_routes.py
from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash

from datetime import datetime, timedelta
from ..models.user import User, db
from ..services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        user = auth_service.authenticate_user(email, password)

        if user:
            token = auth_service.generate_token(user)
            return jsonify({
                'success': True,
                'token': token,
                'user': {
                    'id': str(user.id),  # ← FIX: Convertir UUID a string
                    'email': user.email,
                    'role': user.role,
                    'name': f"{user.first_name} {user.last_name}"
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Credenciales inválidas'
            }), 401

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/register', methods=['POST'])
def register():
    """Registrar nuevo usuario - ACTUALIZADO para admin"""
    try:
        data = request.get_json()

        # Validar que el email no exista
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({
                'success': False,
                'message': 'Email ya registrado'
            }), 400

        # Si hay token de admin, permitir crear cualquier rol
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        current_user = None

        if token:
            current_user = auth_service.verify_token(token)

        # Determinar rol
        role = 'client'  # Por defecto
        if current_user and current_user.role == 'admin':
            # Admin puede crear cualquier rol
            role = data.get('role', 'client')
        elif 'role' in data and data['role'] != 'client':
            # Solo admin puede crear roles no-client
            return jsonify({
                'success': False,
                'message': 'No tienes permisos para crear usuarios con ese rol'
            }), 403

        # Crear usuario
        user = User(
            email=data.get('email'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            phone=data.get('phone'),
            address=data.get('address'),
            role=role,
            is_active=data.get('is_active', True)
        )

        user.set_password(data.get('password'))

        db.session.add(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Usuario creado exitosamente',
            'user': user.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auth_bp.route('/verify', methods=['POST'])
def verify_token():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if user:
            return jsonify({
                'success': True,
                'user': {
                    'id': str(user.id),  # ← FIX: Convertir UUID a string
                    'email': user.email,
                    'role': user.role,
                    'name': f"{user.first_name} {user.last_name}"
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Token inválido'
            }), 401

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/change-password', methods=['PUT'])
def change_password():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user:
            return jsonify({
                'success': False,
                'message': 'Token inválido'
            }), 401

        data = request.get_json()
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if auth_service.change_password(str(user.id), old_password, new_password):  # ← FIX: Convertir UUID a string
            return jsonify({
                'success': True,
                'message': 'Contraseña actualizada exitosamente'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Contraseña actual incorrecta'
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if user:
            return jsonify({
                'success': True,
                'user': user.to_dict()  # ← El método to_dict() ya maneja la conversión UUID
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Token inválido'
            }), 401

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user:
            return jsonify({
                'success': False,
                'message': 'Token inválido'
            }), 401

        data = request.get_json()
        updated_user = auth_service.update_user(str(user.id), data)  # ← FIX: Convertir UUID a string

        if updated_user:
            return jsonify({
                'success': True,
                'message': 'Perfil actualizado exitosamente',
                'user': updated_user.to_dict()  # ← El método to_dict() ya maneja la conversión UUID
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Error al actualizar perfil'
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'auth_service'
    }), 200


@auth_bp.route('/users', methods=['GET'])
def get_all_users():
    """Obtener todos los usuarios (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado. Solo administradores pueden ver usuarios.'
            }), 403

        # Obtener todos los usuarios
        users = User.query.all()
        users_data = [user.to_dict() for user in users]

        return jsonify({
            'success': True,
            'users': users_data,
            'total': len(users_data)
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo usuarios: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Actualizar usuario específico (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado'
            }), 403

        # Obtener datos a actualizar
        data = request.get_json()

        # Buscar usuario a actualizar
        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        # Actualizar campos permitidos
        updatable_fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'role', 'is_active']

        for field in updatable_fields:
            if field in data:
                setattr(target_user, field, data[field])

        # Verificar email único si se está cambiando
        if 'email' in data and data['email'] != target_user.email:
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user and existing_user.id != target_user.id:
                return jsonify({
                    'success': False,
                    'message': 'Email ya está en uso'
                }), 400

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Usuario actualizado exitosamente',
            'user': target_user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auth_bp.route('/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Eliminar usuario (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado'
            }), 403

        # Buscar usuario a eliminar
        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        # No permitir eliminar al propio usuario admin
        if str(target_user.id) == str(user.id):
            return jsonify({
                'success': False,
                'message': 'No puedes eliminar tu propia cuenta'
            }), 400

        # En lugar de eliminar, desactivar el usuario
        target_user.is_active = False
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Usuario desactivado exitosamente'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@auth_bp.route('/users/<user_id>/toggle-status', methods=['PUT'])
def toggle_user_status(user_id):
    """Activar/Desactivar usuario (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado'
            }), 403

        # Buscar usuario
        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        # No permitir desactivar al propio usuario admin
        if str(target_user.id) == str(user.id) and target_user.is_active:
            return jsonify({
                'success': False,
                'message': 'No puedes desactivar tu propia cuenta'
            }), 400

        # Cambiar estado
        target_user.is_active = not target_user.is_active
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Usuario {"activado" if target_user.is_active else "desactivado"} exitosamente',
            'user': target_user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/users/<user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Obtener usuario específico (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado'
            }), 403

        # Buscar usuario
        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        return jsonify({
            'success': True,
            'user': target_user.to_dict()
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/users/stats', methods=['GET'])
def get_users_stats():
    """Obtener estadísticas de usuarios (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado'
            }), 403

        # Calcular estadísticas
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        inactive_users = User.query.filter_by(is_active=False).count()

        # Por roles
        admin_count = User.query.filter_by(role='admin', is_active=True).count()
        vet_count = User.query.filter_by(role='veterinarian', is_active=True).count()
        receptionist_count = User.query.filter_by(role='receptionist', is_active=True).count()
        auxiliary_count = User.query.filter_by(role='auxiliary', is_active=True).count()
        client_count = User.query.filter_by(role='client', is_active=True).count()

        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': inactive_users,
                'by_role': {
                    'admin': admin_count,
                    'veterinarian': vet_count,
                    'receptionist': receptionist_count,
                    'auxiliary': auxiliary_count,
                    'client': client_count
                }
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
