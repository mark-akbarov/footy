from twilio.rest import Client
from twilio.rest.api.v2010.account.message import MessageInstance

from core.config import settings


class TwilioClient:
    def __init__(self):
        self._client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )
        self._messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID

    # TODO: convert to asnyc    
    def send_sms(
        self,
        phone_number: str,
        message: str,
        shorten_urls: bool = False,
    ) -> MessageInstance:
        return self._client.messages.create(
            body=message,
            to=phone_number,
            shorten_urls=shorten_urls,
            messaging_service_sid=self._messaging_service_sid,
        )


twilio_client = TwilioClient()
