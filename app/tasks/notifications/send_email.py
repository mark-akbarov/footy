from celery_config import celery_app
from utils.email import send_mail
from typing import Dict


@celery_app.task(name="send_email_notification")
def send_email_task(to: str, subject: str, template: str, context: Dict[str, str]):
    send_mail(
        mail_to=to,
        mail_subject=subject,
        mail_template_name=template,
        mail_context=context
    )
