import importlib
import smtplib
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.models import ClientEmail, ContactForm

HOST = {'HTTP_HOST': '127.0.0.1'}
CONTACT = '/api/v1/create-contact/'
SUBSCRIBE = '/api/v1/create-email/'
BASE = {'name': 'Ali', 'email': 'ali@example.com', 'message': 'Hello'}


class ApiTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, data, url=CONTACT, **extra):
        return self.client.post(url, data, content_type='application/json', **HOST, **extra)


class ContactFormTests(ApiTestCase):
    def test_only_required_fields(self):
        response = self.post(BASE)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(list(response.json()), ['id', 'name', 'email', 'phone', 'subject', 'message'])
        contact = ContactForm.objects.get()
        self.assertEqual((contact.phone, contact.subject), ('', ''))

    def test_full_payload_keeps_contract(self):
        response = self.post({**BASE, 'phone': '+998 77 012 40 04', 'subject': 'Banner'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['phone'], '+998 77 012 40 04')

    def test_phone_formats(self):
        for phone in ('+998 77 012 40 04', '+998901234567', '(90) 123-45-67'):
            with self.subTest(phone):
                self.assertEqual(self.post({**BASE, 'phone': phone}).status_code, 201)

    def test_invalid_phone_rejected(self):
        self.assertEqual(self.post({**BASE, 'phone': 'call me'}).status_code, 400)
        self.assertEqual(self.post({**BASE, 'phone': '1' * 33}).status_code, 400)

    def test_required_fields(self):
        for missing in ('name', 'email', 'message'):
            with self.subTest(missing):
                self.assertEqual(self.post({k: v for k, v in BASE.items() if k != missing}).status_code, 400)
        self.assertEqual(self.post({**BASE, 'email': 'not-an-email'}).status_code, 400)

    def test_message_length(self):
        self.assertEqual(self.post({**BASE, 'message': 'x' * 3000}).status_code, 201)
        self.assertEqual(self.post({**BASE, 'message': 'x' * 3001}).status_code, 400)
        self.assertEqual(self.post({**BASE, 'message': '   '}).status_code, 400)

    def test_values_are_normalized(self):
        self.post({'name': '  Ali  Valiyev ', 'email': ' ALI@Example.COM ', 'message': ' hi ', 'subject': ' a \n b '})
        contact = ContactForm.objects.get()
        self.assertEqual((contact.name, contact.email, contact.message, contact.subject),
                         ('Ali Valiyev', 'ali@example.com', 'hi', 'a b'))

    def test_html_is_stripped(self):
        self.post({'name': '<b>Ali</b>', 'email': 'a@example.com', 'subject': '<i>Hi</i>',
                   'message': 'Hello <script>alert(1)</script><img src=x onerror=alert(2)> world <b>!</b>'})
        contact = ContactForm.objects.get()
        self.assertEqual((contact.name, contact.subject), ('Ali', 'Hi'))
        self.assertEqual(contact.message, 'Hello  world !')
        self.assertEqual(self.post({**BASE, 'message': '<script>alert(1)</script>'}).status_code, 400)

    def test_internal_fields_cannot_be_set(self):
        self.post({**BASE, 'is_processed': True, 'note': 'x', 'created': '2000-01-01T00:00:00Z'})
        contact = ContactForm.objects.get()
        self.assertEqual((contact.is_processed, contact.note), (False, ''))
        self.assertGreater(contact.created.year, 2000)

    def test_honeypot_returns_201_without_saving(self):
        response = self.post({**BASE, 'website': 'http://spam.example'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactForm.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit_per_minute(self):
        statuses = [self.post(BASE).status_code for _ in range(6)]
        self.assertEqual(statuses, [201] * 5 + [429])
        self.assertEqual(ContactForm.objects.count(), 5)

    def test_rate_limit_uses_forwarded_ip(self):
        for _ in range(5):
            self.post(BASE, HTTP_X_FORWARDED_FOR='9.9.9.9, 1.1.1.1')
        self.assertEqual(self.post(BASE, HTTP_X_FORWARDED_FOR='9.9.9.9, 1.1.1.1').status_code, 429)
        self.assertEqual(self.post(BASE, HTTP_X_FORWARDED_FOR='9.9.9.9, 2.2.2.2').status_code, 201)

    @override_settings(REST_FRAMEWORK={**__import__('django.conf', fromlist=['settings']).settings.REST_FRAMEWORK})
    def test_daily_limit(self):
        from apps.views import ContactDailyThrottle
        with mock.patch.object(ContactDailyThrottle, 'THROTTLE_RATES', {'contact_day': '2/day', 'contact': '100/min'}):
            statuses = [self.post(BASE).status_code for _ in range(3)]
        self.assertEqual(statuses, [201, 201, 429])


@override_settings(CONTACT_NOTIFY_EMAILS=['staff@mga.uz', 'boss@mga.uz'], EMAIL_HOST='smtp.test',
                   DEFAULT_FROM_EMAIL='MGA <no-reply@mga.uz>', ADMIN_BASE_URL='https://api.example.com/')
class NotificationTests(ApiTestCase):
    def submit(self, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.post(data or {**BASE, 'phone': '+998901234567', 'subject': 'Banner'})

    def test_staff_and_customer_emails_are_sent(self):
        self.assertEqual(self.submit().status_code, 201)
        staff, customer = mail.outbox
        contact = ContactForm.objects.get()
        self.assertEqual(staff.subject, "[MGA Reklama] Yangi so'rov: Banner")
        self.assertEqual(staff.to, ['staff@mga.uz', 'boss@mga.uz'])
        for expected in ('Ali', 'ali@example.com', '+998901234567', 'Banner', 'Hello',
                         f'https://api.example.com/admin/apps/contactform/{contact.pk}/change/'):
            self.assertIn(expected, staff.body)
        self.assertEqual(customer.to, ['ali@example.com'])

    def test_default_subject(self):
        self.submit(BASE)
        self.assertEqual(mail.outbox[0].subject, "[MGA Reklama] Yangi so'rov: Website inquiry")

    def test_confirmation_is_translated(self):
        for lang, expected in (('uz', "Assalomu alaykum, Ali"), ('ru', "Здравствуйте, Ali"), ('en', "Hello, Ali"),
                               ('xx', "Hello, Ali")):
            with self.subTest(lang):
                cache.clear()
                mail.outbox.clear()
                self.submit({**BASE, 'lang': lang})
                self.assertIn(expected, mail.outbox[1].body)

    def test_subject_newlines_do_not_break_email(self):
        self.submit({**BASE, 'subject': 'Hi\r\nBcc: evil@example.com'})
        self.assertNotIn('\n', mail.outbox[0].subject)

    def test_smtp_failure_does_not_break_request(self):
        with mock.patch('apps.notifications.send_mail', side_effect=smtplib.SMTPException('down')), \
                self.assertLogs('apps.notifications', level='ERROR') as logs:
            response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactForm.objects.count(), 1)
        self.assertGreaterEqual(len(logs.records), 2)

    def test_telegram_is_used_when_configured_and_failures_are_swallowed(self):
        with override_settings(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42'):
            with mock.patch('apps.notifications.urllib.request.urlopen') as urlopen:
                self.submit()
            self.assertEqual(urlopen.call_count, 1)
            self.assertIn('bot123:abc/sendMessage', urlopen.call_args[0][0].full_url)
            cache.clear()
            with mock.patch('apps.notifications.urllib.request.urlopen', side_effect=OSError('offline')), \
                    self.assertLogs('apps.notifications', level='ERROR'):
                self.assertEqual(self.submit().status_code, 201)

    def test_no_telegram_without_credentials(self):
        with mock.patch('apps.notifications.urllib.request.urlopen') as urlopen:
            self.submit()
        urlopen.assert_not_called()

    def test_customer_confirmation_needs_smtp(self):
        with override_settings(EMAIL_HOST=''):
            self.submit()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['staff@mga.uz', 'boss@mga.uz'])

    def test_spam_sends_nothing(self):
        self.submit({**BASE, 'website': 'x'})
        self.assertEqual(len(mail.outbox), 0)


class SubscriptionTests(ApiTestCase):
    def test_new_and_duplicate(self):
        first = self.post({'email': 'Sub@Example.com '}, SUBSCRIBE)
        self.assertEqual((first.status_code, first.json()['email']), (201, 'sub@example.com'))
        again = self.post({'email': 'sub@example.com'}, SUBSCRIBE)
        self.assertEqual((again.status_code, again.json()['id']), (200, first.json()['id']))
        self.assertEqual(self.post({'email': 'SUB@example.com'}, SUBSCRIBE).status_code, 200)
        self.assertEqual(ClientEmail.objects.count(), 1)

    def test_invalid_email(self):
        self.assertEqual(self.post({'email': 'nope'}, SUBSCRIBE).status_code, 400)
        self.assertEqual(self.post({}, SUBSCRIBE).status_code, 400)

    def test_rate_limit(self):
        statuses = [self.post({'email': f'u{i}@example.com'}, SUBSCRIBE).status_code for i in range(6)]
        self.assertEqual(statuses, [201] * 5 + [429])

    def test_dedupe_migration(self):
        ClientEmail.objects.bulk_create([ClientEmail(email='A@x.uz'), ClientEmail(email='a@x.uz'),
                                         ClientEmail(email='b@x.uz')])
        importlib.import_module('apps.migrations.0019_dedupe_client_emails').dedupe_client_emails(django_apps, None)
        self.assertEqual(list(ClientEmail.objects.order_by('id').values_list('email', flat=True)), ['a@x.uz', 'b@x.uz'])


class AdminTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.uz', 'x'))

    def test_changelist_and_csv_export(self):
        ContactForm.objects.create(name='=cmd|calc', email='a@x.uz', phone='+998901234567', subject='Привет',
                                   message='line1\nline2, "quoted"')
        ContactForm.objects.create(name='Bob', email='b@x.uz', message='m')
        page = self.client.get('/admin/apps/contactform/', **HOST)
        self.assertEqual(page.status_code, 200)
        self.assertIn('name="form-0-is_processed"', page.content.decode())
        response = self.client.post('/admin/apps/contactform/', {
            'action': 'export_selected_csv', '_selected_action': list(ContactForm.objects.values_list('pk', flat=True)),
        }, **HOST)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        body = response.content
        self.assertTrue(body.startswith(b'\xef\xbb\xbf'), 'UTF-8 BOM for Excel')
        text = body.decode('utf-8-sig')
        self.assertIn("'=cmd|calc", text)
        self.assertIn('+998901234567', text)
        self.assertNotIn("'+998", text)
        self.assertIn('Привет', text)

    def test_subscriber_admin(self):
        ClientEmail.objects.create(email='s@x.uz')
        self.assertEqual(self.client.get('/admin/apps/clientemail/?q=s@x', **HOST).status_code, 200)
        response = self.client.post('/admin/apps/clientemail/', {
            'action': 'export_selected_csv', '_selected_action': [ClientEmail.objects.get().pk]}, **HOST)
        self.assertIn('s@x.uz', response.content.decode('utf-8-sig'))
