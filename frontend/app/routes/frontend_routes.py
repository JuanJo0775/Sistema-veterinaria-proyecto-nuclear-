# frontend/app/routes/frontend_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from functools import wraps
import requests

frontend_bp = Blueprint('frontend', __name__ )


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
                    flash('¡Bienvenido!', 'success')
                    return redirect(url_for('frontend.dashboard'))
                else:
                    flash(data.get('message', 'Error al iniciar sesión'), 'error')
            else:
                flash('Credenciales inválidas', 'error')

        except requests.RequestException as e:
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

        return render_template('admin/dashboard.html',
                               inventory_summary=inventory_summary,
                               appointments_today=appointments_today)

    except requests.RequestException as e:
        flash('Error al cargar el dashboard', 'error')
        return render_template('admin/dashboard.html',
                               inventory_summary={},
                               appointments_today=[])


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


# =============== API ENDPOINTS PARA AJAX ===============

@frontend_bp.route('/api/user-info')
@login_required
def user_info():
    """Información del usuario actual"""
    return jsonify({
        'success': True,
        'user': session['user']
    })


@frontend_bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'frontend_service'
    }), 200