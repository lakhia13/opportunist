web: python main.py start
worker: celery -A src.services.scheduler.celery_app worker --loglevel=info
beat: celery -A src.services.scheduler.celery_app beat --loglevel=info
