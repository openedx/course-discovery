
from kombu import Connection, Exchange, Queue


task_exchange = Exchange('course_discovery', type='direct')
task_queue = Queue('task_queue', task_exchange, routing_key='program.metadata')

connection = Connection('redis://:password@redis:6379/0')
producer = connection.Producer()

# producer.publish(
#     {'hello': 'world'},
#     retry=True,
#     exchange=task_queue.exchange,
#     routing_key=task_queue.routing_key,
#     declare=[task_queue],  # declares exchange, queue and binds.
# )





# from kombu import Connection, Exchange, Queue


# task_exchange = Exchange('tasks', type='direct')
# task_queue = Queue('tasks', task_exchange, routing_key='tasks')




# #'redis://:password@redis:6379/0'
# connection = Connection('redis://:password@redis:6379/0')
# producer = connection.Producer()

# with Connection('amqp://') as conn:
#     with conn.channel() as channel:
#         producer = Producer(channel)

# producer.publish(
#     {'hello': 'world'},
#     retry=True,
#     exchange=task_queue.exchange,
#     routing_key=task_queue.routing_key,
#     declare=[task_queue],  # declares exchange, queue and binds.
# )



# task_exchange = Exchange('course_discovery', type='direct')
# task_queue = Queue('task_queue', task_exchange, routing_key='program.metadata')


# producer.publish(
#     {'hello': 'world'},
#     retry=True,
#     exchange=task_queue.exchange,
#     routing_key=task_queue.routing_key,
#     declare=[task_queue],  # declares exchange, queue and binds.
# )

