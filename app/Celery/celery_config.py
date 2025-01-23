from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import Session
from database import SessionLocal  # Assurez-vous d'importer votre session

celery_app = Celery('app')

celery_app.conf.beat_schedule = {
    'effectuer-prelevements-automatiques': {
        'task': 'Celery.tasks.effectuer_prelevement_automatique',
        'schedule': crontab(hour=0, minute=0),
        'args': (SessionLocal(),),
    },
}
