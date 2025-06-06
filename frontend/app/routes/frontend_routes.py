# frontend/app/routes/frontend_routes.py - VERSIÓN CORREGIDA
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from functools import wraps
import requests

frontend_bp = Blueprint('frontend', __name__)


def login_required(f):
    """Decorador para rutas que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('frontend.login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(required_roles):
    """Decorador para rutas que requieren roles específicos"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('frontend.login'))

            user_role = session['user'].get('role')
            if user_role not in required_roles:
                flash('No tienes permisos para acceder a esta página.', 'error')
                return redirect(url_for('frontend.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =============== RUTAS PÚBLICAS ===============

@frontend_bp.route('/')
def index():
    """Página principal/landing"""
    return render_template('index.html')


@frontend_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Llamar al auth service
            auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/login"
            response = requests.post(auth_url, json={
                'email': email,
                'password': password
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Guardar datos del usuario en la sesión
                    session['user'] = data['user']
                    session['token'] = data['token']
                    session.permanent = True

                    flash('¡Bienvenido!', 'success')
                    print(f"🔐 Usuario logueado: {data['user']}")

                    return redirect(url_for('frontend.dashboard'))
                else:
                    flash(data.get('message', 'Error al iniciar sesión'), 'error')
            else:
                flash('Credenciales inválidas', 'error')

        except requests.RequestException as e:
            print(f"❌ Error de conexión: {e}")
            flash('Error de conexión con el servidor', 'error')

    return render_template('auth/login.html')


@frontend_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro"""
    if request.method == 'POST':
        user_data = {
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name'),
            'phone': request.form.get('phone'),
            'address': request.form.get('address'),
            'role': 'client'
        }

        try:
            auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/register"
            response = requests.post(auth_url, json=user_data, timeout=10)

            if response.status_code == 201:
                flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
                return redirect(url_for('frontend.login'))
            else:
                data = response.json()
                flash(data.get('message', 'Error al registrarse'), 'error')

        except requests.RequestException as e:
            flash('Error de conexión con el servidor', 'error')

    return render_template('auth/register.html')


@frontend_bp.route('/logout')
def logout():
    """Cerrar sesión"""
    session.clear()
    flash('Sesión cerrada exitosamente', 'info')
    return redirect(url_for('frontend.index'))


# =============== RUTAS PROTEGIDAS ===============

@frontend_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal - redirige según el rol"""
    user_role = session['user'].get('role')
    print(f"🔄 Dashboard redirect para rol: {user_role}")

    if user_role == 'admin':
        return redirect(url_for('frontend.admin_dashboard'))
    elif user_role == 'veterinarian':
        return redirect(url_for('frontend.veterinarian_dashboard'))
    elif user_role == 'receptionist':
        return redirect(url_for('frontend.receptionist_dashboard'))
    elif user_role == 'auxiliary':
        return redirect(url_for('frontend.auxiliary_dashboard'))
    elif user_role == 'client':
        return redirect(url_for('frontend.client_dashboard'))
    else:
        flash('Rol de usuario no válido', 'error')
        return redirect(url_for('frontend.logout'))


# =============== DASHBOARDS POR ROL ===============

@frontend_bp.route('/admin/dashboard')
@role_required(['admin'])
def admin_dashboard():
    """Dashboard principal para administradores"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Obtener resumen del inventario
        inventory_summary = {}
        try:
            inventory_url = f"{current_app.config['INVENTORY_SERVICE_URL']}/inventory/summary"
            inventory_response = requests.get(inventory_url, headers=headers, timeout=10)
            if inventory_response.status_code == 200:
                inventory_data = inventory_response.json()
                if inventory_data.get('success'):
                    inventory_summary = inventory_data.get('summary', {})
        except Exception as e:
            print(f"⚠️ Error obteniendo inventario: {e}")

        # Obtener estadísticas de citas
        appointments_today = []
        try:
            appointments_url = f"{current_app.config['APPOINTMENT_SERVICE_URL']}/appointments/today"
            appointments_response = requests.get(appointments_url, headers=headers, timeout=10)
            if appointments_response.status_code == 200:
                appointments_data = appointments_response.json()
                if appointments_data.get('success'):
                    appointments_today = appointments_data.get('appointments', [])
        except Exception as e:
            print(f"⚠️ Error obteniendo citas: {e}")

        # Preparar datos para el template
        user = session.get('user', {})
        template_data = {
            'inventory_summary': inventory_summary,
            'appointments_today': appointments_today,
            'user': user,
            'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or 'Administrador',
            'user_role': user.get('role', 'admin').title(),
            'user_initial': user.get('first_name', 'A')[0].upper() if user.get('first_name') else 'A'
        }

        return render_template('admin/dashboard.html', **template_data)

    except Exception as e:
        print(f"❌ Error en admin dashboard: {e}")
        flash('Error al cargar el dashboard', 'error')
        user = session.get('user', {})
        return render_template('admin/dashboard.html',
                               inventory_summary={},
                               appointments_today=[],
                               user=user,
                               user_name='Administrador',
                               user_role='Admin',
                               user_initial='A')


# =============== RUTAS ESPECÍFICAS PARA SECCIONES ADMIN ===============

@frontend_bp.route('/admin/users')
@role_required(['admin'])
def admin_users():
    """Página de gestión de usuarios - ÚNICA DEFINICIÓN"""
    try:
        user = session.get('user', {})
        template_data = {
            'user': user,
            'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or 'Administrador',
            'user_role': user.get('role', 'admin').title(),
            'user_initial': user.get('first_name', 'A')[0].upper() if user.get('first_name') else 'A'
        }

        return render_template('admin/sections/users-management.html', **template_data)

    except Exception as e:
        print(f"❌ Error en admin users: {e}")
        flash('Error al cargar la gestión de usuarios', 'error')
        return redirect(url_for('frontend.admin_dashboard'))


@frontend_bp.route('/admin/inventory')
@role_required(['admin'])
def admin_inventory():
    """Página de gestión de inventario"""
    user = session.get('user', {})
    template_data = {
        'user': user,
        'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or 'Administrador',
        'user_role': user.get('role', 'admin').title(),
        'user_initial': user.get('first_name', 'A')[0].upper() if user.get('first_name') else 'A'
    }
    return render_template('admin/sections/inventory-management.html', **template_data)


@frontend_bp.route('/admin/appointments')
@role_required(['admin'])
def admin_appointments():
    """Página de gestión de citas"""
    user = session.get('user', {})
    template_data = {
        'user': user,
        'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or 'Administrador',
        'user_role': user.get('role', 'admin').title(),
        'user_initial': user.get('first_name', 'A')[0].upper() if user.get('first_name') else 'A'
    }
    return render_template('admin/sections/appointments-management.html', **template_data)


# =============== OTROS DASHBOARDS ===============

@frontend_bp.route('/client/dashboard')
@role_required(['client'])
def client_dashboard():
    """Dashboard para clientes"""
    return render_template('client/dashboard.html')


@frontend_bp.route('/veterinarian/dashboard')
@role_required(['veterinarian'])
def veterinarian_dashboard():
    """Dashboard para veterinarios"""
    return render_template('veterinarian/dashboard.html')


@frontend_bp.route('/receptionist/dashboard')
@role_required(['receptionist'])
def receptionist_dashboard():
    """Dashboard para recepcionistas"""
    return render_template('receptionist/dashboard.html')


@frontend_bp.route('/auxiliary/dashboard')
@role_required(['auxiliary'])
def auxiliary_dashboard():
    """Dashboard para auxiliares"""
    return render_template('auxiliary/dashboard.html')


# =============== API ENDPOINTS PARA AJAX ===============

@frontend_bp.route('/api/user-info')
@login_required
def user_info():
    """Información del usuario actual"""
    return jsonify({
        'success': True,
        'user': session['user']
    })


@frontend_bp.route('/api/dashboard-data')
@login_required
def dashboard_data():
    """Datos para el dashboard (AJAX)"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Datos del inventario
        inventory_data = {}
        try:
            inventory_url = f"{current_app.config['INVENTORY_SERVICE_URL']}/inventory/summary"
            inventory_response = requests.get(inventory_url, headers=headers, timeout=5)
            if inventory_response.status_code == 200:
                inv_json = inventory_response.json()
                if inv_json.get('success'):
                    inventory_data = inv_json.get('summary', {})
        except:
            pass

        # Citas de hoy
        appointments_count = 0
        try:
            appointments_url = f"{current_app.config['APPOINTMENT_SERVICE_URL']}/appointments/today"
            appointments_response = requests.get(appointments_url, headers=headers, timeout=5)
            if appointments_response.status_code == 200:
                app_json = appointments_response.json()
                if app_json.get('success'):
                    appointments_count = len(app_json.get('appointments', []))
        except:
            pass

        return jsonify({
            'success': True,
            'data': {
                'total_pets': 0,
                'appointments_today': appointments_count,
                'low_stock_count': inventory_data.get('low_stock_count', 0),
                'inventory_value': inventory_data.get('total_inventory_value', 0),
                'notifications_count': 0
            }
        })

    except Exception as e:
        print(f"❌ Error obteniendo datos del dashboard: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@frontend_bp.route('/api/admin/users')
@role_required(['admin'])
def api_get_users():
    """API endpoint para obtener usuarios (para AJAX del frontend)"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Obtener usuarios desde Auth Service
        auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/users"
        response = requests.get(auth_url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return jsonify(data)
        elif response.status_code == 403:
            return jsonify({
                'success': False,
                'message': 'Token de autorización inválido o expirado'
            }), 403
        else:
            return jsonify({
                'success': False,
                'message': f'Error del Auth Service: {response.status_code}'
            }), response.status_code

    except requests.RequestException as e:
        print(f"❌ Error conectando con Auth Service: {e}")
        return jsonify({
            'success': False,
            'message': 'Error de conexión con el servicio de autenticación'
        }), 500
    except Exception as e:
        print(f"❌ Error en api_get_users: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@frontend_bp.route('/api/admin/users', methods=['POST'])
@role_required(['admin'])
def api_create_user():
    """Crear nuevo usuario"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}
        data = request.get_json()

        # Crear usuario en Auth Service
        auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/register"
        response = requests.post(auth_url, json=data, headers=headers, timeout=10)

        if response.status_code == 201:
            return jsonify(response.json())
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith(
                'application/json') else {}
            return jsonify({
                'success': False,
                'message': error_data.get('message', f'Error del Auth Service: {response.status_code}')
            }), response.status_code

    except requests.RequestException as e:
        print(f"❌ Error conectando con Auth Service: {e}")
        return jsonify({
            'success': False,
            'message': 'Error de conexión con el servicio de autenticación'
        }), 500
    except Exception as e:
        print(f"❌ Error en api_create_user: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@frontend_bp.route('/api/admin/users/<user_id>', methods=['PUT'])
@role_required(['admin'])
def api_update_user(user_id):
    """Actualizar usuario específico"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}
        data = request.get_json()

        # Actualizar usuario en Auth Service
        auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/users/{user_id}"
        response = requests.put(auth_url, json=data, headers=headers, timeout=10)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith(
                'application/json') else {}
            return jsonify({
                'success': False,
                'message': error_data.get('message', f'Error del Auth Service: {response.status_code}')
            }), response.status_code

    except requests.RequestException as e:
        print(f"❌ Error conectando con Auth Service: {e}")
        return jsonify({
            'success': False,
            'message': 'Error de conexión con el servicio de autenticación'
        }), 500
    except Exception as e:
        print(f"❌ Error en api_update_user: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@frontend_bp.route('/api/admin/users/<user_id>/toggle-status', methods=['PUT'])
@role_required(['admin'])
def api_toggle_user_status(user_id):
    """Activar/Desactivar usuario"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Cambiar estado en Auth Service
        auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/users/{user_id}/toggle-status"
        response = requests.put(auth_url, headers=headers, timeout=10)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith(
                'application/json') else {}
            return jsonify({
                'success': False,
                'message': error_data.get('message', f'Error del Auth Service: {response.status_code}')
            }), response.status_code

    except requests.RequestException as e:
        print(f"❌ Error conectando con Auth Service: {e}")
        return jsonify({
            'success': False,
            'message': 'Error de conexión con el servicio de autenticación'
        }), 500
    except Exception as e:
        print(f"❌ Error en api_toggle_user_status: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@frontend_bp.route('/api/admin/users/<user_id>', methods=['DELETE'])
@role_required(['admin'])
def api_delete_user(user_id):
    """Eliminar usuario definitivamente"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Verificar que no sea el usuario actual
        current_user = session.get('user', {})
        if current_user.get('id') == user_id:
            return jsonify({
                'success': False,
                'message': 'No puedes eliminar tu propia cuenta'
            }), 400

        # Eliminar usuario en Auth Service
        auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/users/{user_id}"
        response = requests.delete(auth_url, headers=headers, timeout=10)

        if response.status_code == 200:
            return jsonify(response.json())
        elif response.status_code == 400:
            # Error de validación (como intentar eliminar propia cuenta)
            error_data = response.json() if response.headers.get('content-type', '').startswith(
                'application/json') else {}
            return jsonify({
                'success': False,
                'message': error_data.get('message', 'No se puede eliminar este usuario')
            }), 400
        elif response.status_code == 404:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith(
                'application/json') else {}
            return jsonify({
                'success': False,
                'message': error_data.get('message', f'Error del Auth Service: {response.status_code}')
            }), response.status_code

    except requests.RequestException as e:
        print(f"❌ Error conectando con Auth Service: {e}")
        return jsonify({
            'success': False,
            'message': 'Error de conexión con el servicio de autenticación'
        }), 500
    except Exception as e:
        print(f"❌ Error en api_delete_user: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@frontend_bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'frontend_service'
    }), 200