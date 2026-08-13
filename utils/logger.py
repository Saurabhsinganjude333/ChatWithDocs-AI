import logging, sys
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file=None, level="INFO"):
    logger = logging.getLogger(name)
    if logger.handlers: return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s", "%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(sys.stdout); ch.setFormatter(fmt); logger.addHandler(ch)
    if log_file:
        fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=2); fh.setFormatter(fmt); logger.addHandler(fh)
    logger.propagate = False
    return logger
