from celery_config import celery_app
from utils.email import send_mail
from typing import Dict


@celery_app.task(name="send_email_notification")
def send_email_task(to_email: str, subject: str, template: str, context: Dict[str, str], to_name: str = None):
    """Celery task to send an email."""
    return send_mail(
        to_email=to_email,
        subject=subject,
        template_name=template,
        context=context,
        to_name=to_name
    )
