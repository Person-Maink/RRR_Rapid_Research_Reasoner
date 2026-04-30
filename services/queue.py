import json
import logging
from collections.abc import Callable

from services.environment import RABBITMQ_QUEUE, RABBITMQ_URL

LOGGER = logging.getLogger(__name__)


class RabbitMQClient:
    def __init__(self, url: str = RABBITMQ_URL, queue_name: str = RABBITMQ_QUEUE):
        self.url = url
        self.queue_name = queue_name

    def _connect(self):
        import pika

        return pika.BlockingConnection(pika.URLParameters(self.url))

    def publish_job(self, job_id: str) -> None:
        import pika

        with self._connect() as connection:
            channel = connection.channel()
            channel.queue_declare(queue=self.queue_name, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=self.queue_name,
                body=json.dumps({"job_id": job_id}).encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),
            )

    def consume_jobs(self, callback: Callable[[str], None]) -> None:
        connection = self._connect()
        channel = connection.channel()
        channel.queue_declare(queue=self.queue_name, durable=True)
        channel.basic_qos(prefetch_count=1)

        def handle_message(ch, method, _properties, body):
            payload = json.loads(body.decode("utf-8"))
            job_id = payload["job_id"]
            try:
                callback(job_id)
            except Exception:
                LOGGER.exception("Job processing failed", extra={"job_id": job_id})
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=self.queue_name, on_message_callback=handle_message)
        LOGGER.info("Worker waiting for jobs", extra={"queue": self.queue_name})
        channel.start_consuming()
