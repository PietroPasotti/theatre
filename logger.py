import logging
import os

# FIXME! whatever we're logging will get to juju_log!
logger = logging.getLogger("theatre")
logging.basicConfig(level=os.getenv("LOGLEVEL", logging.WARNING))
logger.info(f"logger initialized with {logger.level}")
