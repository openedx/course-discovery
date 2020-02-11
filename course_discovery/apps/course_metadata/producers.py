
from kombu import Connection, Exchange, Queue


task_exchange = Exchange('course_discovery', type='direct')
task_queue = Queue('task_queue', task_exchange, routing_key='program.metadata')

connection = Connection('redis://:password@redis:6379/0')
producer = connection.Producer()
