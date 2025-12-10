from loguru import logger
import os

LOG_PATH = "logs/app.log"

# Création du dossier logs si nécessaire
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# Configuration du logger
logger.add(
    LOG_PATH,
    rotation="10 MB",       # rotation des fichiers
    retention="10 days",    # on garde les logs 10 jours
    compression="zip",      # zip des anciens logs
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "{message}",
)

__all__ = ["logger"]
