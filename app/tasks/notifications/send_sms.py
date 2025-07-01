from app.celery_config import celery_app
from utils.sms import twilio_client


@celery_app.task(name="send_sms_notification")
def send_sms_task(phone: str, message: str):
    twilio_client.send_sms(phone_number=phone, message=message)
