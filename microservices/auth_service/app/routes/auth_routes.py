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
    """Eliminar usuario definitivamente (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado. Solo administradores pueden eliminar usuarios.'
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

        # Guardar información del usuario para el log
        user_info = f"{target_user.first_name} {target_user.last_name} ({target_user.email})"

        # ELIMINAR DEFINITIVAMENTE de la base de datos
        db.session.delete(target_user)
        db.session.commit()

        print(f"🗑️ Usuario eliminado definitivamente: {user_info} por {user.email}")

        return jsonify({
            'success': True,
            'message': f'Usuario {user_info} eliminado definitivamente del sistema'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error eliminando usuario: {e}")
        return jsonify({
            'success': False,
            'message': f'Error interno al eliminar usuario: {str(e)}'
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


# AGREGAR AL FINAL DE: microservices/auth_service/app/routes/auth_routes.py

# =============== SCHEDULES MANAGEMENT ENDPOINTS ===============

@auth_bp.route('/schedules', methods=['GET'])
def get_all_schedules():
    """Obtener todos los horarios (solo para admin)"""
    try:
        # Verificar token de administrador
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = auth_service.verify_token(token)

        if not user or user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Acceso denegado. Solo administradores pueden ver horarios.'
            }), 403

        # Obtener usuarios con roles que pueden tener horarios
        staff_users = User.query.filter(
            User.role.in_(['veterinarian', 'receptionist', 'auxiliary']),
            User.is_active == True
        ).all()

        # Crear estructura de horarios
        schedules_data = []
        for staff_user in staff_users:
            user_schedule = {
                'user_id': str(staff_user.id),
                'user_name': f"{staff_user.first_name} {staff_user.last_name}",
                'user_email': staff_user.email,
                'user_role': staff_user.role,
                'phone': staff_user.phone,
                'weekly_schedule': generate_user_schedule(staff_user.role)
            }
            schedules_data.append(user_schedule)

        return jsonify({
            'success': True,
            'schedules': schedules_data,
            'total': len(schedules_data)
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo horarios: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500




@auth_bp.route('/schedules/<user_id>', methods=['GET'])
def get_user_schedule(user_id):
    """Obtener horario de un usuario específico"""
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

        if target_user.role not in ['veterinarian', 'receptionist', 'auxiliary']:
            return jsonify({
                'success': False,
                'message': 'Este usuario no puede tener horarios asignados'
            }), 400

        # Generar horario
        schedule_data = {
            'user_id': str(target_user.id),
            'user_name': f"{target_user.first_name} {target_user.last_name}",
            'user_email': target_user.email,
            'user_role': target_user.role,
            'phone': target_user.phone,
            'weekly_schedule': generate_user_schedule(target_user.role)
        }

        return jsonify({
            'success': True,
            'schedule': schedule_data
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo horario del usuario: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/schedules/<user_id>', methods=['PUT'])
def update_user_schedule(user_id):
    """Actualizar horario de un usuario"""
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

        # Obtener datos del horario
        data = request.get_json()
        weekly_schedule = data.get('weekly_schedule', {})

        # Validar formato del horario
        if not validate_schedule_format(weekly_schedule):
            return jsonify({
                'success': False,
                'message': 'Formato de horario inválido'
            }), 400

        # En una implementación real, aquí se guardarían en una tabla schedules
        # Por ahora, simularemos que se guardó correctamente

        print(f"📅 Horario actualizado para {target_user.first_name} {target_user.last_name}")
        print(f"   Horario: {weekly_schedule}")

        return jsonify({
            'success': True,
            'message': f'Horario actualizado exitosamente para {target_user.first_name} {target_user.last_name}',
            'schedule': {
                'user_id': str(target_user.id),
                'user_name': f"{target_user.first_name} {target_user.last_name}",
                'weekly_schedule': weekly_schedule
            }
        }), 200

    except Exception as e:
        print(f"❌ Error actualizando horario: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# =============== FUNCIONES AUXILIARES PARA HORARIOS ===============

def generate_user_schedule(role):
    """Generar horario específico según el rol"""
    if role == 'veterinarian':
        return {
            'monday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'tuesday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'wednesday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00',
                          'break_end': '13:00'},
            'thursday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00',
                         'break_end': '13:00'},
            'friday': {'start': '08:00', 'end': '16:00', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'saturday': {'start': '08:00', 'end': '12:00', 'active': True, 'break_start': '', 'break_end': ''},
            'sunday': {'start': '', 'end': '', 'active': False, 'break_start': '', 'break_end': ''}
        }
    elif role == 'receptionist':
        return {
            'monday': {'start': '07:30', 'end': '17:30', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'tuesday': {'start': '07:30', 'end': '17:30', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'wednesday': {'start': '07:30', 'end': '17:30', 'active': True, 'break_start': '12:00',
                          'break_end': '13:00'},
            'thursday': {'start': '07:30', 'end': '17:30', 'active': True, 'break_start': '12:00',
                         'break_end': '13:00'},
            'friday': {'start': '07:30', 'end': '18:00', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'saturday': {'start': '08:00', 'end': '13:00', 'active': True, 'break_start': '', 'break_end': ''},
            'sunday': {'start': '', 'end': '', 'active': False, 'break_start': '', 'break_end': ''}
        }
    else:  # auxiliary
        return {
            'monday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'tuesday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'wednesday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00',
                          'break_end': '13:00'},
            'thursday': {'start': '08:00', 'end': '17:00', 'active': True, 'break_start': '12:00',
                         'break_end': '13:00'},
            'friday': {'start': '08:00', 'end': '16:00', 'active': True, 'break_start': '12:00', 'break_end': '13:00'},
            'saturday': {'start': '', 'end': '', 'active': False, 'break_start': '', 'break_end': ''},
            'sunday': {'start': '', 'end': '', 'active': False, 'break_start': '', 'break_end': ''}
        }


def validate_schedule_format(schedule):
    """Validar formato del horario"""
    try:
        required_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        if not isinstance(schedule, dict):
            return False

        for day in required_days:
            if day not in schedule:
                return False

            day_data = schedule[day]
            if not isinstance(day_data, dict):
                return False

            # Validar campos requeridos
            required_fields = ['start', 'end', 'active']
            for field in required_fields:
                if field not in day_data:
                    return False

            # Si está activo, debe tener horarios válidos
            if day_data['active']:
                if not day_data['start'] or not day_data['end']:
                    return False

                # Validar formato de hora (HH:MM)
                try:
                    start_parts = day_data['start'].split(':')
                    end_parts = day_data['end'].split(':')

                    if len(start_parts) != 2 or len(end_parts) != 2:
                        return False

                    start_hour, start_min = int(start_parts[0]), int(start_parts[1])
                    end_hour, end_min = int(end_parts[0]), int(end_parts[1])

                    if not (0 <= start_hour <= 23 and 0 <= start_min <= 59):
                        return False
                    if not (0 <= end_hour <= 23 and 0 <= end_min <= 59):
                        return False

                    # Validar que hora de inicio sea menor que hora de fin
                    start_minutes = start_hour * 60 + start_min
                    end_minutes = end_hour * 60 + end_min

                    if start_minutes >= end_minutes:
                        return False

                except (ValueError, IndexError):
                    return False

        return True

    except Exception as e:
        print(f"❌ Error validando formato de horario: {e}")
        return False
