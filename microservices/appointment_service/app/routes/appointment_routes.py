# microservices/appointment_service/app/routes/appointment_routes.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from ..models.appointment import Appointment
from ..models.schedule import VeterinarianSchedule
from .. import db
from ..services.appointment_service import AppointmentService

appointment_bp = Blueprint('appointments', __name__)
appointment_service = AppointmentService()


@appointment_bp.route('/create', methods=['POST'])
def create_appointment():
    try:
        data = request.get_json()

        # Validaciones básicas
        required_fields = ['pet_id', 'veterinarian_id', 'client_id', 'appointment_date', 'appointment_time']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Campo requerido: {field}'
                }), 400

        # Validar disponibilidad
        if not appointment_service.check_availability(
                data.get('veterinarian_id'),
                data.get('appointment_date'),
                data.get('appointment_time')
        ):
            return jsonify({
                'success': False,
                'message': 'Horario no disponible'
            }), 400

        appointment = appointment_service.create_appointment(data)

        # Notificar al recepcionista (llamada asíncrona)
        appointment_service.notify_new_appointment(appointment.id)

        return jsonify({
            'success': True,
            'appointment_id': str(appointment.id),
            'message': 'Cita creada exitosamente',
            'appointment': appointment.to_dict()
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/schedules', methods=['POST'])
def create_schedule():
    """Crear horario para veterinario"""
    try:
        data = request.get_json()

        # Validaciones básicas
        required_fields = ['veterinarian_id', 'day_of_week', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'Campo requerido: {field}'
                }), 400

        # Validar day_of_week
        day_of_week = data.get('day_of_week')
        if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
            return jsonify({
                'success': False,
                'message': 'day_of_week debe ser un entero entre 0 (Lunes) y 6 (Domingo)'
            }), 400

        # Verificar si ya existe un horario para ese día
        existing_schedule = VeterinarianSchedule.query.filter_by(
            veterinarian_id=data.get('veterinarian_id'),
            day_of_week=day_of_week
        ).first()

        if existing_schedule:
            return jsonify({
                'success': False,
                'message': 'Ya existe un horario para ese día'
            }), 400

        # Convertir horarios a objetos time
        try:
            start_time = datetime.strptime(data.get('start_time'), '%H:%M').time()
            end_time = datetime.strptime(data.get('end_time'), '%H:%M').time()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Formato de hora inválido. Use HH:MM'
            }), 400

        # Validar que start_time sea menor que end_time
        if start_time >= end_time:
            return jsonify({
                'success': False,
                'message': 'La hora de inicio debe ser menor que la hora de fin'
            }), 400

        # Crear nuevo horario
        schedule = VeterinarianSchedule(
            veterinarian_id=data.get('veterinarian_id'),
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            is_available=data.get('is_available', True)
        )

        db.session.add(schedule)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Horario creado exitosamente',
            'schedule': schedule.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }), 500


@appointment_bp.route('/schedules/<vet_id>', methods=['GET'])
def get_veterinarian_schedules(vet_id):
    """Obtener horarios de un veterinario"""
    try:
        schedules = VeterinarianSchedule.get_by_veterinarian(vet_id)

        return jsonify({
            'success': True,
            'schedules': [schedule.to_dict() for schedule in schedules],
            'veterinarian_id': vet_id
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/schedules', methods=['GET'])
def get_all_schedules():
    """Obtener todos los horarios"""
    try:
        schedules = VeterinarianSchedule.query.filter_by(is_available=True).all()

        return jsonify({
            'success': True,
            'schedules': [schedule.to_dict() for schedule in schedules],
            'total': len(schedules)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/schedules/<schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    """Actualizar horario"""
    try:
        data = request.get_json()

        schedule = VeterinarianSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({
                'success': False,
                'message': 'Horario no encontrado'
            }), 404

        # Actualizar campos permitidos
        if 'start_time' in data:
            try:
                schedule.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Formato de hora inválido para start_time. Use HH:MM'
                }), 400

        if 'end_time' in data:
            try:
                schedule.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Formato de hora inválido para end_time. Use HH:MM'
                }), 400

        if 'is_available' in data:
            schedule.is_available = data['is_available']

        # Validar que start_time sea menor que end_time
        if schedule.start_time >= schedule.end_time:
            return jsonify({
                'success': False,
                'message': 'La hora de inicio debe ser menor que la hora de fin'
            }), 400

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Horario actualizado exitosamente',
            'schedule': schedule.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }), 500


@appointment_bp.route('/schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Eliminar/desactivar horario"""
    try:
        schedule = VeterinarianSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({
                'success': False,
                'message': 'Horario no encontrado'
            }), 404

        # En lugar de eliminar, desactivar
        schedule.is_available = False
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Horario desactivado exitosamente'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error interno: {str(e)}'
        }), 500



@appointment_bp.route('/available-slots', methods=['GET'])
def get_available_slots():
    try:
        veterinarian_id = request.args.get('veterinarian_id')
        date = request.args.get('date')

        if not veterinarian_id or not date:
            return jsonify({
                'success': False,
                'message': 'Parámetros requeridos: veterinarian_id, date'
            }), 400

        slots = appointment_service.get_available_slots(veterinarian_id, date)

        return jsonify({
            'success': True,
            'available_slots': slots,
            'date': date,
            'veterinarian_id': veterinarian_id
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/by-veterinarian/<vet_id>', methods=['GET'])
def get_appointments_by_vet(vet_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        appointments = appointment_service.get_appointments_by_veterinarian(
            vet_id, start_date, end_date
        )

        return jsonify({
            'success': True,
            'appointments': appointments,
            'veterinarian_id': vet_id
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/by-client/<client_id>', methods=['GET'])
def get_appointments_by_client(client_id):
    try:
        status = request.args.get('status')

        appointments = appointment_service.get_appointments_by_client(client_id, status)

        return jsonify({
            'success': True,
            'appointments': appointments,
            'client_id': client_id
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/update/<appointment_id>', methods=['PUT'])
def update_appointment(appointment_id):
    try:
        data = request.get_json()

        appointment = appointment_service.update_appointment(appointment_id, data)

        if appointment:
            return jsonify({
                'success': True,
                'message': 'Cita actualizada exitosamente',
                'appointment': appointment.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/cancel/<appointment_id>', methods=['PUT'])
def cancel_appointment(appointment_id):
    try:
        appointment = appointment_service.cancel_appointment(appointment_id)

        if appointment:
            return jsonify({
                'success': True,
                'message': 'Cita cancelada exitosamente',
                'appointment': appointment.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/confirm/<appointment_id>', methods=['PUT'])
def confirm_appointment(appointment_id):
    try:
        appointment = appointment_service.confirm_appointment(appointment_id)

        if appointment:
            return jsonify({
                'success': True,
                'message': 'Cita confirmada exitosamente',
                'appointment': appointment.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/complete/<appointment_id>', methods=['PUT'])
def complete_appointment(appointment_id):
    try:
        appointment = appointment_service.complete_appointment(appointment_id)

        if appointment:
            return jsonify({
                'success': True,
                'message': 'Cita marcada como completada',
                'appointment': appointment.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/today', methods=['GET'])
def get_today_appointments():
    try:
        today = datetime.now().date()
        appointments = Appointment.query.filter(
            Appointment.appointment_date == today,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).order_by(Appointment.appointment_time).all()

        return jsonify({
            'success': True,
            'appointments': [apt.to_dict() for apt in appointments],
            'date': today.isoformat()
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# =============== RUTAS FALTANTES PARA APPOINTMENT SERVICE ===============

@appointment_bp.route('/appointments', methods=['GET'])
def get_all_appointments():
    """Obtener todas las citas con filtros opcionales"""
    try:
        # Parámetros de filtro
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        veterinarian_id = request.args.get('veterinarian_id')
        client_id = request.args.get('client_id')
        status = request.args.get('status')
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int, default=0)

        # Construir query base
        query = Appointment.query

        # Aplicar filtros
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Appointment.appointment_date >= start_date_obj)
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Formato de fecha inválido para start_date. Use YYYY-MM-DD'
                }), 400

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Appointment.appointment_date <= end_date_obj)
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Formato de fecha inválido para end_date. Use YYYY-MM-DD'
                }), 400

        if veterinarian_id:
            query = query.filter(Appointment.veterinarian_id == veterinarian_id)

        if client_id:
            query = query.filter(Appointment.client_id == client_id)

        if status:
            query = query.filter(Appointment.status == status)

        # Ordenar por fecha y hora más recientes
        query = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())

        # Aplicar paginación si se especifica
        if limit:
            query = query.offset(offset).limit(limit)

        appointments = query.all()

        return jsonify({
            'success': True,
            'appointments': [appointment.to_dict() for appointment in appointments],
            'total': len(appointments),
            'filters_applied': {
                'start_date': start_date,
                'end_date': end_date,
                'veterinarian_id': veterinarian_id,
                'client_id': client_id,
                'status': status
            }
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo citas: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/<appointment_id>', methods=['GET'])
def get_appointment_by_id(appointment_id):
    """Obtener cita específica por ID"""
    try:
        appointment = Appointment.query.get(appointment_id)

        if not appointment:
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404

        return jsonify({
            'success': True,
            'appointment': appointment.to_dict()
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo cita: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/<appointment_id>', methods=['DELETE'])
def delete_appointment(appointment_id):
    """Eliminar cita definitivamente"""
    try:
        appointment = Appointment.query.get(appointment_id)

        if not appointment:
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404

        # Guardar información para el log
        appointment_info = f"Cita de {appointment.appointment_date} a las {appointment.appointment_time}"

        # Eliminar de la base de datos
        db.session.delete(appointment)
        db.session.commit()

        print(f"🗑️ Cita eliminada: {appointment_info}")

        return jsonify({
            'success': True,
            'message': f'Cita eliminada exitosamente: {appointment_info}'
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error eliminando cita: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/search', methods=['GET'])
def search_appointments():
    """Buscar citas por múltiples criterios"""
    try:
        search_term = request.args.get('q', '')

        if not search_term:
            return jsonify({
                'success': False,
                'message': 'Parámetro de búsqueda requerido'
            }), 400

        # Buscar en múltiples campos (esto requiere un JOIN con datos de usuario/mascota)
        # Por ahora buscaremos en los campos disponibles
        appointments = Appointment.query.filter(
            db.or_(
                Appointment.reason.ilike(f'%{search_term}%'),
                Appointment.notes.ilike(f'%{search_term}%'),
                # Aquí se podrían agregar más campos con JOINs
            )
        ).order_by(Appointment.appointment_date.desc()).all()

        return jsonify({
            'success': True,
            'appointments': [appointment.to_dict() for appointment in appointments],
            'total': len(appointments),
            'search_term': search_term
        }), 200

    except Exception as e:
        print(f"❌ Error buscando citas: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/statistics', methods=['GET'])
def get_appointments_statistics():
    """Obtener estadísticas detalladas de citas"""
    try:
        from datetime import datetime, timedelta

        # Estadísticas básicas
        total_appointments = Appointment.query.count()

        # Citas de hoy
        today = datetime.now().date()
        appointments_today = Appointment.query.filter(
            Appointment.appointment_date == today
        ).count()

        # Citas de esta semana
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        appointments_this_week = Appointment.query.filter(
            Appointment.appointment_date >= week_start,
            Appointment.appointment_date <= week_end
        ).count()

        # Citas de este mes
        month_start = today.replace(day=1)
        appointments_this_month = Appointment.query.filter(
            Appointment.appointment_date >= month_start,
            Appointment.appointment_date <= today
        ).count()

        # Por estado
        scheduled_count = Appointment.query.filter_by(status='scheduled').count()
        confirmed_count = Appointment.query.filter_by(status='confirmed').count()
        completed_count = Appointment.query.filter_by(status='completed').count()
        cancelled_count = Appointment.query.filter_by(status='cancelled').count()

        # Próximas citas (próximos 7 días)
        next_week = today + timedelta(days=7)
        upcoming_appointments = Appointment.query.filter(
            Appointment.appointment_date > today,
            Appointment.appointment_date <= next_week,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).count()

        return jsonify({
            'success': True,
            'statistics': {
                'total_appointments': total_appointments,
                'appointments_today': appointments_today,
                'appointments_this_week': appointments_this_week,
                'appointments_this_month': appointments_this_month,
                'upcoming_appointments': upcoming_appointments,
                'by_status': {
                    'scheduled': scheduled_count,
                    'confirmed': confirmed_count,
                    'completed': completed_count,
                    'cancelled': cancelled_count
                },
                'completion_rate': (completed_count / total_appointments * 100) if total_appointments > 0 else 0,
                'cancellation_rate': (cancelled_count / total_appointments * 100) if total_appointments > 0 else 0
            }
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/upcoming', methods=['GET'])
def get_upcoming_appointments():
    """Obtener próximas citas"""
    try:
        days_ahead = request.args.get('days', 7, type=int)
        limit = request.args.get('limit', type=int)

        # Calcular fechas
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)

        # Construir query
        query = Appointment.query.filter(
            Appointment.appointment_date > today,
            Appointment.appointment_date <= end_date,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).order_by(Appointment.appointment_date, Appointment.appointment_time)

        if limit:
            query = query.limit(limit)

        appointments = query.all()

        return jsonify({
            'success': True,
            'appointments': [appointment.to_dict() for appointment in appointments],
            'total': len(appointments),
            'date_range': {
                'start': today.isoformat(),
                'end': end_date.isoformat(),
                'days_ahead': days_ahead
            }
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo próximas citas: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/by-date/<date_string>', methods=['GET'])
def get_appointments_by_date(date_string):
    """Obtener citas de una fecha específica"""
    try:
        # Convertir string a fecha
        try:
            appointment_date = datetime.strptime(date_string, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Formato de fecha inválido. Use YYYY-MM-DD'
            }), 400

        # Obtener citas de esa fecha
        appointments = Appointment.query.filter(
            Appointment.appointment_date == appointment_date
        ).order_by(Appointment.appointment_time).all()

        return jsonify({
            'success': True,
            'appointments': [appointment.to_dict() for appointment in appointments],
            'total': len(appointments),
            'date': date_string
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo citas por fecha: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/by-status/<status>', methods=['GET'])
def get_appointments_by_status(status):
    """Obtener citas por estado"""
    try:
        # Validar estado
        valid_statuses = ['scheduled', 'confirmed', 'completed', 'cancelled']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'message': f'Estado inválido. Estados válidos: {", ".join(valid_statuses)}'
            }), 400

        appointments = Appointment.query.filter_by(
            status=status
        ).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()

        return jsonify({
            'success': True,
            'appointments': [appointment.to_dict() for appointment in appointments],
            'total': len(appointments),
            'status': status
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo citas por estado: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/weekly-schedule', methods=['GET'])
def get_weekly_schedule():
    """Obtener horario semanal de citas"""
    try:
        # Parámetros opcionales
        week_offset = request.args.get('week_offset', 0, type=int)  # 0 = esta semana, 1 = próxima, -1 = anterior
        veterinarian_id = request.args.get('veterinarian_id')

        # Calcular fechas de la semana
        today = datetime.now().date()
        days_to_monday = today.weekday()
        monday = today - timedelta(days=days_to_monday) + timedelta(weeks=week_offset)
        sunday = monday + timedelta(days=6)

        # Construir query
        query = Appointment.query.filter(
            Appointment.appointment_date >= monday,
            Appointment.appointment_date <= sunday
        )

        if veterinarian_id:
            query = query.filter(Appointment.veterinarian_id == veterinarian_id)

        appointments = query.order_by(
            Appointment.appointment_date,
            Appointment.appointment_time
        ).all()

        # Organizar por días de la semana
        weekly_schedule = {}
        for i in range(7):
            day_date = monday + timedelta(days=i)
            day_name = day_date.strftime('%A').lower()
            weekly_schedule[day_name] = {
                'date': day_date.isoformat(),
                'appointments': []
            }

        # Llenar con citas
        for appointment in appointments:
            day_name = appointment.appointment_date.strftime('%A').lower()
            if day_name in weekly_schedule:
                weekly_schedule[day_name]['appointments'].append(appointment.to_dict())

        return jsonify({
            'success': True,
            'weekly_schedule': weekly_schedule,
            'week_info': {
                'monday': monday.isoformat(),
                'sunday': sunday.isoformat(),
                'week_offset': week_offset,
                'total_appointments': len(appointments)
            }
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo horario semanal: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/conflicts', methods=['GET'])
def check_appointment_conflicts():
    """Verificar conflictos de horarios"""
    try:
        veterinarian_id = request.args.get('veterinarian_id')
        appointment_date = request.args.get('appointment_date')
        appointment_time = request.args.get('appointment_time')
        exclude_appointment_id = request.args.get('exclude_appointment_id')  # Para ediciones

        if not all([veterinarian_id, appointment_date, appointment_time]):
            return jsonify({
                'success': False,
                'message': 'Parámetros requeridos: veterinarian_id, appointment_date, appointment_time'
            }), 400

        # Convertir fecha y hora
        try:
            date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            time_obj = datetime.strptime(appointment_time, '%H:%M').time()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Formato de fecha/hora inválido'
            }), 400

        # Buscar conflictos
        query = Appointment.query.filter(
            Appointment.veterinarian_id == veterinarian_id,
            Appointment.appointment_date == date_obj,
            Appointment.appointment_time == time_obj,
            Appointment.status.in_(['scheduled', 'confirmed'])
        )

        # Excluir cita específica si se está editando
        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)

        conflicting_appointments = query.all()

        has_conflict = len(conflicting_appointments) > 0

        return jsonify({
            'success': True,
            'has_conflict': has_conflict,
            'conflicting_appointments': [apt.to_dict() for apt in conflicting_appointments],
            'checked_slot': {
                'veterinarian_id': veterinarian_id,
                'date': appointment_date,
                'time': appointment_time
            }
        }), 200

    except Exception as e:
        print(f"❌ Error verificando conflictos: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/bulk-update', methods=['PUT'])
def bulk_update_appointments():
    """Actualizar múltiples citas en lote"""
    try:
        data = request.get_json()
        appointment_ids = data.get('appointment_ids', [])
        updates = data.get('updates', {})

        if not appointment_ids:
            return jsonify({
                'success': False,
                'message': 'Lista de IDs de citas requerida'
            }), 400

        if not updates:
            return jsonify({
                'success': False,
                'message': 'Datos de actualización requeridos'
            }), 400

        # Campos permitidos para actualización en lote
        allowed_fields = ['status', 'notes']
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return jsonify({
                'success': False,
                'message': f'Campos de actualización inválidos. Permitidos: {", ".join(allowed_fields)}'
            }), 400

        # Actualizar citas
        updated_appointments = []
        for appointment_id in appointment_ids:
            appointment = Appointment.query.get(appointment_id)
            if appointment:
                for field, value in filtered_updates.items():
                    setattr(appointment, field, value)

                appointment.updated_at = datetime.utcnow()
                updated_appointments.append(appointment.to_dict())

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'{len(updated_appointments)} citas actualizadas exitosamente',
            'updated_appointments': updated_appointments,
            'applied_updates': filtered_updates
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error en actualización en lote: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/appointments/reports/veterinarian/<vet_id>', methods=['GET'])
def get_veterinarian_appointment_report(vet_id):
    """Generar reporte de citas por veterinario"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Query base
        query = Appointment.query.filter_by(veterinarian_id=vet_id)

        # Aplicar filtros de fecha
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Appointment.appointment_date >= start_date_obj)

        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Appointment.appointment_date <= end_date_obj)

        appointments = query.order_by(
            Appointment.appointment_date.desc(),
            Appointment.appointment_time.desc()
        ).all()

        # Calcular estadísticas
        total_appointments = len(appointments)
        completed_appointments = len([a for a in appointments if a.status == 'completed'])
        cancelled_appointments = len([a for a in appointments if a.status == 'cancelled'])

        # Agrupar por fecha
        appointments_by_date = {}
        for appointment in appointments:
            date_str = appointment.appointment_date.isoformat()
            if date_str not in appointments_by_date:
                appointments_by_date[date_str] = []
            appointments_by_date[date_str].append(appointment.to_dict())

        return jsonify({
            'success': True,
            'report': {
                'veterinarian_id': vet_id,
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'statistics': {
                    'total_appointments': total_appointments,
                    'completed_appointments': completed_appointments,
                    'cancelled_appointments': cancelled_appointments,
                    'completion_rate': (
                                completed_appointments / total_appointments * 100) if total_appointments > 0 else 0,
                    'cancellation_rate': (
                                cancelled_appointments / total_appointments * 100) if total_appointments > 0 else 0
                },
                'appointments_by_date': appointments_by_date,
                'all_appointments': [appointment.to_dict() for appointment in appointments]
            }
        }), 200

    except ValueError as e:
        return jsonify({
            'success': False,
            'message': 'Formato de fecha inválido. Use YYYY-MM-DD'
        }), 400
    except Exception as e:
        print(f"❌ Error generando reporte: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@appointment_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'appointment_service'
    }), 200