# microservices/auth_service/app/models/__init__.py
from .user import User, db

__all__ = ['User', 'db']