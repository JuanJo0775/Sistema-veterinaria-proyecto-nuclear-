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
                    session.permanent = True  # Hacer la sesión permanente

                    flash('¡Bienvenido!', 'success')

                    # Debug: verificar qué se guardó en la sesión
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
            'role': 'client'  # Por defecto todos los registros son clientes
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

    if user_role == 'client':
        return redirect(url_for('frontend.client_dashboard'))
    elif user_role == 'veterinarian':
        return redirect(url_for('frontend.veterinarian_dashboard'))
    elif user_role == 'receptionist':
        return redirect(url_for('frontend.receptionist_dashboard'))
    elif user_role == 'auxiliary':
        return redirect(url_for('frontend.auxiliary_dashboard'))
    elif user_role == 'admin':
        return redirect(url_for('frontend.admin_dashboard'))
    else:
        flash('Rol de usuario no válido', 'error')
        return redirect(url_for('frontend.logout'))


# =============== DASHBOARDS POR ROL ===============

@frontend_bp.route('/client/dashboard')
@role_required(['client'])
def client_dashboard():
    """Dashboard para clientes"""
    try:
        # Obtener citas del cliente
        user_id = session['user']['id']
        appointments_url = f"{current_app.config['APPOINTMENT_SERVICE_URL']}/appointments/by-client/{user_id}"
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        appointments_response = requests.get(appointments_url, headers=headers, timeout=10)
        appointments = []
        if appointments_response.status_code == 200:
            appointments_data = appointments_response.json()
            if appointments_data.get('success'):
                appointments = appointments_data.get('appointments', [])

        # Obtener mascotas del cliente
        pets_url = f"{current_app.config['MEDICAL_SERVICE_URL']}/medical/pets/owner/{user_id}"
        pets_response = requests.get(pets_url, headers=headers, timeout=10)
        pets = []
        if pets_response.status_code == 200:
            pets_data = pets_response.json()
            if pets_data.get('success'):
                pets = pets_data.get('pets', [])

        return render_template('client/dashboard.html',
                               appointments=appointments,
                               pets=pets)

    except requests.RequestException as e:
        flash('Error al cargar el dashboard', 'error')
        return render_template('client/dashboard.html', appointments=[], pets=[])


@frontend_bp.route('/veterinarian/dashboard')
@role_required(['veterinarian'])
def veterinarian_dashboard():
    """Dashboard para veterinarios"""
    try:
        user_id = session['user']['id']
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Obtener citas del veterinario para hoy
        appointments_url = f"{current_app.config['APPOINTMENT_SERVICE_URL']}/appointments/by-veterinarian/{user_id}"
        appointments_response = requests.get(appointments_url, headers=headers, timeout=10)
        appointments = []
        if appointments_response.status_code == 200:
            appointments_data = appointments_response.json()
            if appointments_data.get('success'):
                appointments = appointments_data.get('appointments', [])

        return render_template('veterinarian/dashboard.html', appointments=appointments)

    except requests.RequestException as e:
        flash('Error al cargar el dashboard', 'error')
        return render_template('veterinarian/dashboard.html', appointments=[])


@frontend_bp.route('/receptionist/dashboard')
@role_required(['receptionist'])
def receptionist_dashboard():
    """Dashboard para recepcionistas"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Obtener citas de hoy
        appointments_url = f"{current_app.config['APPOINTMENT_SERVICE_URL']}/appointments/today"
        appointments_response = requests.get(appointments_url, headers=headers, timeout=10)
        appointments = []
        if appointments_response.status_code == 200:
            appointments_data = appointments_response.json()
            if appointments_data.get('success'):
                appointments = appointments_data.get('appointments', [])

        return render_template('receptionist/dashboard.html', appointments=appointments)

    except requests.RequestException as e:
        flash('Error al cargar el dashboard', 'error')
        return render_template('receptionist/dashboard.html', appointments=[])


@frontend_bp.route('/auxiliary/dashboard')
@role_required(['auxiliary'])
def auxiliary_dashboard():
    """Dashboard para auxiliares"""
    try:
        headers = {'Authorization': f"Bearer {session.get('token')}"}

        # Obtener alertas de inventario
        inventory_url = f"{current_app.config['INVENTORY_SERVICE_URL']}/inventory/alerts/low-stock"
        inventory_response = requests.get(inventory_url, headers=headers, timeout=10)
        low_stock_items = []
        if inventory_response.status_code == 200:
            inventory_data = inventory_response.json()
            if inventory_data.get('success'):
                low_stock_items = inventory_data.get('low_stock_medications', [])

        return render_template('auxiliary/dashboard.html', low_stock_items=low_stock_items)

    except requests.RequestException as e:
        flash('Error al cargar el dashboard', 'error')
        return render_template('auxiliary/dashboard.html', low_stock_items=[])


@frontend_bp.route('/admin/dashboard')
@role_required(['admin'])
def admin_dashboard():
    """Dashboard para administradores"""
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
        user_id = session['user']['id']

        # Datos del inventario
        inventory_url = f"{current_app.config['INVENTORY_SERVICE_URL']}/inventory/summary"
        inventory_response = requests.get(inventory_url, headers=headers, timeout=5)
        inventory_data = {}
        if inventory_response.status_code == 200:
            inv_json = inventory_response.json()
            if inv_json.get('success'):
                inventory_data = inv_json.get('summary', {})

        # Citas de hoy
        appointments_url = f"{current_app.config['APPOINTMENT_SERVICE_URL']}/appointments/today"
        appointments_response = requests.get(appointments_url, headers=headers, timeout=5)
        appointments_count = 0
        if appointments_response.status_code == 200:
            app_json = appointments_response.json()
            if app_json.get('success'):
                appointments_count = len(app_json.get('appointments', []))

        # Notificaciones (sin llamar si es null)
        notifications_count = 0
        if user_id and user_id != 'null':
            try:
                notifications_url = f"{current_app.config['NOTIFICATION_SERVICE_URL']}/notifications/user/{user_id}?unread_only=true"
                notifications_response = requests.get(notifications_url, headers=headers, timeout=5)
                if notifications_response.status_code == 200:
                    notif_json = notifications_response.json()
                    if notif_json.get('success'):
                        notifications_count = len(notif_json.get('notifications', []))
            except:
                pass  # Si falla, dejar en 0

        return jsonify({
            'success': True,
            'data': {
                'total_pets': 0,  # Implementar endpoint para mascotas totales
                'appointments_today': appointments_count,
                'low_stock_count': inventory_data.get('low_stock_count', 0),
                'inventory_value': inventory_data.get('total_inventory_value', 0),
                'notifications_count': notifications_count
            }
        })

    except Exception as e:
        print(f"❌ Error obteniendo datos del dashboard: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# =============== RUTAS DE GESTIÓN ===============

@frontend_bp.route('/appointments')
@login_required
def appointments():
    """Lista de citas"""
    return render_template('appointments/list.html')


@frontend_bp.route('/pets')
@login_required
def pets():
    """Lista de mascotas"""
    return render_template('pets/list.html')


@frontend_bp.route('/inventory')
@role_required(['admin', 'auxiliary', 'veterinarian'])
def inventory():
    """Gestión de inventario"""
    return render_template('inventory/list.html')


@frontend_bp.route('/medical-records')
@role_required(['veterinarian', 'admin'])
def medical_records():
    """Historias clínicas"""
    return render_template('medical/list.html')


@frontend_bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'frontend_service'
    }), 200


@frontend_bp.route('/admin/section/<section_name>')
@role_required(['admin'])
def load_admin_section(section_name):
    """Cargar sección específica del panel admin"""
    try:
        # Mapeo de secciones a templates
        section_templates = {
            'users': 'admin/sections/users-management.html',
            'inventory': 'admin/sections/inventory-management.html',
            'appointments': 'admin/sections/appointments-management.html',
            'pets': 'admin/sections/pets-management.html',
            'medical-records': 'admin/sections/medical-records.html',
            'notifications': 'admin/sections/notifications-center.html',
            'messaging': 'admin/sections/messaging-system.html',
            'financial-reports': 'admin/sections/financial-reports.html',
            'schedules': 'admin/sections/schedules-management.html',
            'settings': 'admin/sections/settings.html'
        }

        template_path = section_templates.get(section_name)

        if not template_path:
            return jsonify({
                'success': False,
                'message': f'Sección {section_name} no encontrada'
            }), 404

        # Verificar si el template existe
        try:
            content = render_template(template_path)
            return jsonify({
                'success': True,
                'content': content,
                'section': section_name
            })
        except Exception as e:
            # Si el template no existe, devolver placeholder
            placeholder_content = f"""
            <div style="text-align: center; padding: 60px 20px; color: #52B788;">
                <h2 style="color: #2D6A4F; margin-bottom: 20px;">🔧 {section_name.replace('-', ' ').title()}</h2>
                <p style="color: #52B788; font-size: 1.1rem;">Esta sección está en desarrollo...</p>
                <p>Template: {template_path}</p>
                <button onclick="navigateToSection('dashboard')" 
                        style="background: #52B788; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; margin-top: 20px;">
                    Volver al Dashboard
                </button>
            </div>
            """
            return jsonify({
                'success': True,
                'content': placeholder_content,
                'section': section_name,
                'is_placeholder': True
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500