from __future__ import annotations
import smtplib,logging
from email.message import EmailMessage
from . import settings

log=logging.getLogger(__name__)

def notify_new_lead(lead):
    if not settings.SMTP_HOST:
        return False
    msg=EmailMessage()
    msg['Subject']='SpaceBox — new website enquiry #'+str(lead.id)
    msg['From']=settings.SMTP_FROM
    msg['To']=settings.NOTIFY_EMAIL
    msg.set_content('\n'.join([
        f'Enquiry ID: {lead.id}',f'Name: {lead.name}',f'Phone: {lead.phone}',
        f'Email: {lead.email}',f'Project type: {lead.project_type}',
        f'Location: {lead.location}',f'Budget: {lead.budget}',
        f'Notes:\n{lead.message}',
    ]))
    try:
        with smtplib.SMTP(settings.SMTP_HOST,settings.SMTP_PORT,timeout=8) as client:
            if settings.SMTP_STARTTLS:client.starttls()
            if settings.SMTP_USER:client.login(settings.SMTP_USER,settings.SMTP_PASSWORD)
            client.send_message(msg)
        return True
    except Exception:
        log.exception('Lead notification failed; lead remains stored in database')
        return False
