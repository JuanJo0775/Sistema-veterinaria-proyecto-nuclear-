# frontend/app/routes/frontend_routes.py - VERSIÓN ARREGLADA
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
    """Página de gestión de usuarios"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Obtener todos los usuarios desde Auth Service
        users_data = []
        users_stats = {
            'total': 0,
            'veterinarians': 0,
            'clients': 0,
            'active': 0
        }

        try:
            auth_url = f"{current_app.config['AUTH_SERVICE_URL']}/auth/users"
            response = requests.get(auth_url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    users_data = data.get('users', [])

                    # Calcular estadísticas
                    users_stats['total'] = len(users_data)
                    users_stats['veterinarians'] = len([u for u in users_data if u.get('role') == 'veterinarian'])
                    users_stats['clients'] = len([u for u in users_data if u.get('role') == 'client'])
                    users_stats['active'] = len([u for u in users_data if u.get('is_active', True)])

                    print(f"✅ Usuarios cargados: {users_stats['total']}")
                else:
                    print(f"⚠️ Error en respuesta de usuarios: {data.get('message')}")
            else:
                print(f"⚠️ Error HTTP obteniendo usuarios: {response.status_code}")

        except Exception as e:
            print(f"⚠️ Error conectando con Auth Service: {e}")

        user = session.get('user', {})
        template_data = {
            'users_data': users_data,
            'users_stats': users_stats,
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
    return render_template('admin/sections/inventory-management.html',
                           user=session.get('user', {}))


@frontend_bp.route('/admin/appointments')
@role_required(['admin'])
def admin_appointments():
    """Página de gestión de citas"""
    return render_template('admin/sections/appointments-management.html',
                           user=session.get('user', {}))


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


@frontend_bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'frontend_service'
    }), 200

@frontend_bp.route('/admin/users')
@role_required(['admin'])
def admin_users():
    """Página de gestión de usuarios"""
    try:
        user = session.get('user', {})
        template_data = {
            'user': user,
            'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or 'Administrador',
            'user_role': user.get('role', 'admin').title(),
            'user_initial': user.get('first_name', 'A')[0].upper() if user.get('first_name') else 'A'
        }

        return render_template('admin/users.html', **template_data)

    except Exception as e:
        print(f"❌ Error en admin users: {e}")
        flash('Error al cargar la gestión de usuarios', 'error')
        return redirect(url_for('frontend.admin_dashboard'))


# También actualizar la ruta del dashboard para usar el template base
@frontend_bp.route('/admin/dashboard')
@role_required(['admin'])
def admin_dashboard():
    """Dashboard para administradores - mantener como está"""
    # El dashboard ya está funcionando bien, no lo tocamos
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        print(f"🔐 Admin dashboard - Usuario: {session.get('user')}")
        print(f"🔐 Token: {session.get('token')[:50]}..." if session.get('token') else "No token")

        # Obtener resumen del inventario
        inventory_url = f"{current_app.config['INVENTORY_SERVICE_URL']}/inventory/summary"
        inventory_response = requests.get(inventory_url, headers=headers, timeout=10)
        inventory_summary = {}
        if inventory_response.status_code == 200:
            inventory_data = inventory_response.json()
            if inventory_data.get('success'):
                inventory_summary = inventory_data.get('summary', {})

        # Obtener estadísticas de citas
        appointments_url = f"{current_app.config['APPOINTMENT_SERVICE_URL']}/appointments/today"
        appointments_response = requests.get(appointments_url, headers=headers, timeout=10)
        appointments_today = []
        if appointments_response.status_code == 200:
            appointments_data = appointments_response.json()
            if appointments_data.get('success'):
                appointments_today = appointments_data.get('appointments', [])

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

    except requests.RequestException as e:
        print(f"❌ Error en admin dashboard: {e}")
        flash('Error al cargar el dashboard', 'error')
        return render_template('admin/dashboard.html',
                               inventory_summary={},
                               appointments_today=[],
                               user=session.get('user'))