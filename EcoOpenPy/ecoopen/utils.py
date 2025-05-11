import logging
import threading

# Thread-safe logging handler
logging_lock = threading.Lock()

def log_message(level, message):
    """Log a message with thread-safe locking."""
    with logging_lock:
        if level == "INFO":
            logging.info(message)
        elif level == "WARNING":
            logging.warning(message)
        elif level == "ERROR":
            logging.error(message)