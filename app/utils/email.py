from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from string import Template
from core.config import settings
from typing import Dict
import os
import aiofiles
import aiosmtplib

MAIL_SMTP_SERVER = settings.MAIL_SMTP_SERVER
MAIL_SMTP_PORT = settings.MAIL_SMTP_PORT
MAIL_SMTP_USERNAME = settings.MAIL_USER
MAIL_SMTP_PASSWORD = settings.MAIL_PASSWORD
MAIL_DISPLAY_NAME = "Footy"


def send_mail(
    mail_to: str,
    mail_subject: str,
    mail_template_name: str,
    mail_context: Dict[str, str]
):

    current_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(current_dir, 'mail_templates')
    file_path = os.path.join(templates_dir, f"{mail_template_name}.html")

    with open(f"{file_path}") as file:
        template_content = file.read()

    template = Template(template_content)
    email_body = template.substitute(mail_context)

    # Create the email message
    message = MIMEMultipart()
    message['From'] = f"{MAIL_DISPLAY_NAME} <{MAIL_SMTP_USERNAME}>"
    message['To'] = mail_to
    message['Subject'] = mail_subject

    message.attach(MIMEText(email_body, 'html'))

    with smtplib.SMTP(MAIL_SMTP_SERVER, MAIL_SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(MAIL_SMTP_USERNAME, MAIL_SMTP_PASSWORD)
        server.sendmail(MAIL_SMTP_USERNAME, [message['To']], message.as_string())


async def send_verification_code_email(email: str, email_body: str):
    message = MIMEMultipart()
    message['From'] = f"{MAIL_DISPLAY_NAME} <{MAIL_SMTP_USERNAME}>"
    message['To'] = email
    message['Subject'] = "Carriving verification code"
    message.attach(MIMEText(email_body, 'plain'))
    with smtplib.SMTP(MAIL_SMTP_SERVER, MAIL_SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(MAIL_SMTP_USERNAME, MAIL_SMTP_PASSWORD)
        server.sendmail(MAIL_SMTP_USERNAME, [email], message.as_string())
