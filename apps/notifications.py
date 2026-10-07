import json
import logging
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

DEFAULT_SUBJECT = 'Website inquiry'


def _admin_url(contact):
    return settings.ADMIN_BASE_URL.rstrip('/') + reverse('admin:apps_contactform_change', args=[contact.pk])


def _staff_text(contact):
    created = timezone.localtime(contact.created).strftime('%Y-%m-%d %H:%M')
    return (
        f"Ism: {contact.name}\n"
        f"Email: {contact.email}\n"
        f"Telefon: {contact.phone or '-'}\n"
        f"Mavzu: {contact.subject or '-'}\n"
        f"Vaqt: {created}\n\n"
        f"Xabar:\n{contact.message}\n\n"
        f"Admin: {_admin_url(contact)}"
    )


def _email_staff(contact, lang):
    if not settings.CONTACT_NOTIFY_EMAILS:
        return
    send_mail(f"[MGA Reklama] Yangi so'rov: {contact.subject or DEFAULT_SUBJECT}", _staff_text(contact),
              settings.DEFAULT_FROM_EMAIL, settings.CONTACT_NOTIFY_EMAILS)


def _telegram_staff(contact, lang):
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return
    payload = json.dumps({'chat_id': settings.TELEGRAM_CHAT_ID,
                          'text': f"Yangi so'rov\n\n{_staff_text(contact)}"[:4000]}).encode()
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage', data=payload,
        headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(request, timeout=5).close()


def _confirm_customer(contact, lang):
    if not settings.EMAIL_HOST:
        return
    with translation.override(lang):
        subject = _("We received your request")
        body = _("Hello, %(name)s!\n\nThank you for contacting MGA Reklama. "
                 "Your request has been received and we will contact you soon.\n\nMGA Reklama") % {'name': contact.name}
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [contact.email])


def notify_new_contact(contact, lang='en'):
    """Send every notification independently; a failure must never break the request."""
    for send in (_email_staff, _telegram_staff, _confirm_customer):
        try:
            send(contact, lang)
        except Exception:
            logger.exception("Contact notification %s failed for contact #%s", send.__name__, contact.pk)
