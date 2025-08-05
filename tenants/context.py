# tenants/context.py
from threading import local
import logging

logger = logging.getLogger(__name__)
_thread_local = local()

def get_current_db():
    """Get the current database alias, returns None if not set"""
    return getattr(_thread_local, 'current_db', None)

def set_current_db(db_alias):
    """Set the current database alias"""
    _thread_local.current_db = db_alias
    logger.debug(f"Thread-local database set to: {db_alias}")

def clear_current_db():
    """Clear the current database context"""
    if hasattr(_thread_local, 'current_db'):
        delattr(_thread_local, 'current_db')
        logger.debug("Thread-local database context cleared")

def has_db_context():
    """Check if database context is set"""
    return hasattr(_thread_local, 'current_db')