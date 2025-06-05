# frontend/app/services/api_client.py
import requests
from flask import current_app, session
import logging


class APIClient:
    def __init__(self):
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

    def init_app(self, app):
        """Inicializar el cliente API con la aplicación Flask"""
        self.app = app
        # Configurar headers por defecto
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def get_headers(self, include_auth=True):
        """Obtener headers con autenticación si está disponible"""
        headers = {}
        if include_auth and 'token' in session:
            headers['Authorization'] = f"Bearer {session['token']}"
        return headers

    def make_request(self, method, service_url, endpoint, data=None, include_auth=True, timeout=10):
        """Realizar petición HTTP a un microservicio"""
        try:
            url = f"{service_url}{endpoint}"
            headers = self.get_headers(include_auth)

            self.logger.info(f"Making {method} request to {url}")

            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, timeout=timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, headers=headers, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Método HTTP no soportado: {method}")

            # Log de la respuesta
            self.logger.info(f"Response status: {response.status_code}")

            return response

        except requests.RequestException as e:
            self.logger.error(f"Error en petición a {service_url}{endpoint}: {str(e)}")
            raise

    # =============== AUTH SERVICE ===============

    def login(self, email, password):
        """Autenticar usuario"""
        auth_url = current_app.config['AUTH_SERVICE_URL']
        return self.make_request('POST', auth_url, '/auth/login', {
            'email': email,
            'password': password
        }, include_auth=False)

    def register(self, user_data):
        """Registrar nuevo usuario"""
        auth_url = current_app.config['AUTH_SERVICE_URL']
        return self.make_request('POST', auth_url, '/auth/register', user_data, include_auth=False)

    def verify_token(self):
        """Verificar token de autenticación"""
        auth_url = current_app.config['AUTH_SERVICE_URL']
        return self.make_request('POST', auth_url, '/auth/verify')

    # =============== APPOINTMENT SERVICE ===============

    def get_appointments_by_client(self, client_id):
        """Obtener citas de un cliente"""
        appointment_url = current_app.config['APPOINTMENT_SERVICE_URL']
        return self.make_request('GET', appointment_url, f'/appointments/by-client/{client_id}')

    def get_appointments_by_veterinarian(self, vet_id, start_date=None, end_date=None):
        """Obtener citas de un veterinario"""
        appointment_url = current_app.config['APPOINTMENT_SERVICE_URL']
        endpoint = f'/appointments/by-veterinarian/{vet_id}'
        if start_date and end_date:
            endpoint += f'?start_date={start_date}&end_date={end_date}'
        return self.make_request('GET', appointment_url, endpoint)

    def get_today_appointments(self):
        """Obtener citas de hoy"""
        appointment_url = current_app.config['APPOINTMENT_SERVICE_URL']
        return self.make_request('GET', appointment_url, '/appointments/today')

    def create_appointment(self, appointment_data):
        """Crear nueva cita"""
        appointment_url = current_app.config['APPOINTMENT_SERVICE_URL']
        return self.make_request('POST', appointment_url, '/appointments/create', appointment_data)

    def get_available_slots(self, veterinarian_id, date):
        """Obtener slots disponibles"""
        appointment_url = current_app.config['APPOINTMENT_SERVICE_URL']
        endpoint = f'/appointments/available-slots?veterinarian_id={veterinarian_id}&date={date}'
        return self.make_request('GET', appointment_url, endpoint)

    # =============== MEDICAL SERVICE ===============

    def get_pets_by_owner(self, owner_id):
        """Obtener mascotas de un propietario"""
        medical_url = current_app.config['MEDICAL_SERVICE_URL']
        return self.make_request('GET', medical_url, f'/medical/pets/owner/{owner_id}')

    def create_pet(self, pet_data):
        """Crear nueva mascota"""
        medical_url = current_app.config['MEDICAL_SERVICE_URL']
        return self.make_request('POST', medical_url, '/medical/pets', pet_data)

    def get_medical_records_by_pet(self, pet_id):
        """Obtener historias clínicas de una mascota"""
        medical_url = current_app.config['MEDICAL_SERVICE_URL']
        return self.make_request('GET', medical_url, f'/medical/records/pet/{pet_id}')

    def create_medical_record(self, record_data):
        """Crear nueva historia clínica"""
        medical_url = current_app.config['MEDICAL_SERVICE_URL']
        return self.make_request('POST', medical_url, '/medical/records', record_data)

    # =============== INVENTORY SERVICE ===============

    def get_inventory_summary(self):
        """Obtener resumen del inventario"""
        inventory_url = current_app.config['INVENTORY_SERVICE_URL']
        return self.make_request('GET', inventory_url, '/inventory/summary')

    def get_low_stock_medications(self):
        """Obtener medicamentos con stock bajo"""
        inventory_url = current_app.config['INVENTORY_SERVICE_URL']
        return self.make_request('GET', inventory_url, '/inventory/alerts/low-stock')

    def get_medications(self):
        """Obtener todos los medicamentos"""
        inventory_url = current_app.config['INVENTORY_SERVICE_URL']
        return self.make_request('GET', inventory_url, '/inventory/medications')

    def create_medication(self, medication_data):
        """Crear nuevo medicamento"""
        inventory_url = current_app.config['INVENTORY_SERVICE_URL']
        return self.make_request('POST', inventory_url, '/inventory/medications', medication_data)

    def update_stock(self, medication_id, quantity_change, reason):
        """Actualizar stock de medicamento"""
        inventory_url = current_app.config['INVENTORY_SERVICE_URL']
        return self.make_request('PUT', inventory_url, '/inventory/update-stock', {
            'medication_id': medication_id,
            'quantity_change': quantity_change,
            'reason': reason
        })

    # =============== NOTIFICATION SERVICE ===============

    def get_user_notifications(self, user_id, unread_only=False):
        """Obtener notificaciones de un usuario"""
        notification_url = current_app.config['NOTIFICATION_SERVICE_URL']
        endpoint = f'/notifications/user/{user_id}'
        if unread_only:
            endpoint += '?unread_only=true'
        return self.make_request('GET', notification_url, endpoint)

    def mark_notification_as_read(self, notification_id, user_id):
        """Marcar notificación como leída"""
        notification_url = current_app.config['NOTIFICATION_SERVICE_URL']
        return self.make_request('PUT', notification_url, f'/notifications/mark-read/{notification_id}', {
            'user_id': user_id
        })

    def send_appointment_reminder(self, user_id, appointment_details, email=None, phone=None):
        """Enviar recordatorio de cita"""
        notification_url = current_app.config['NOTIFICATION_SERVICE_URL']
        return self.make_request('POST', notification_url, '/notifications/send-reminder', {
            'user_id': user_id,
            'appointment_details': appointment_details,
            'email': email,
            'phone': phone
        })