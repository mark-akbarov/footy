import os
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from core.config import settings

# Initialize Jinja2 environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates", "email")
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


class EmailManager:
    @staticmethod
    def render_template(template_name: str, context: Dict[str, str]) -> str:
        """Render an email template with the given context."""
        template = env.get_template(f"{template_name}.html")
        return template.render(**context)

    @staticmethod
    def send_email(
            to_email: str,
            subject: str,
            html_content: str,
            to_name: Optional[str] = None
    ) -> bool:
        """Send an email using Brevo API v3."""
        try:
            # Configure API key
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = settings.BREVO_API_KEY

            # Create an instance of the API class
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration)
            )

            # Prepare the email
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=[{
                    "email": to_email,
                    "name": to_name or to_email
                }],
                sender={
                    "name": settings.MAIL_FROM_NAME,
                    "email": settings.MAIL_FROM
                },
                subject=subject,
                html_content=html_content
            )

            # Make the API call
            result = api_instance.send_transac_email(send_smtp_email)
            print(f"Email sent successfully. Message ID: {result}")
            return True

        except ApiException as e:
            print(f"Error sending email via Brevo API:")
            print(f"Status code: {e.status}")
            print(f"Reason: {e.reason}")
            print(f"Body: {e.body}")
            return False
        except Exception as e:
            print(f"Unexpected error sending email: {e}")
            return False


def send_mail(
        to_email: str,
        subject: str,
        template_name: str,
        context: Dict[str, str],
        to_name: Optional[str] = None
) -> bool:
    """High-level function to send an email using a template."""
    email_manager = EmailManager()

    try:
        # Render the template
        html_content = email_manager.render_template(template_name, context)

        # Send the email
        return email_manager.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            to_name=to_name
        )
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False