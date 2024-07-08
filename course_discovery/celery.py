from celery import Celery


# TEMP: This code will be removed by ARCH-BOM on 4/22/24
# ddtrace allows celery task logs to be traced by the dd agent.
# TODO: remove this code.
try:
    from ddtrace import patch
    patch(celery=True)
except ImportError:
    pass

app = Celery('discovery')
# namespace='CELERY' means all celery-related configuration keys should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


if __name__ == '__main__':
    app.start()
