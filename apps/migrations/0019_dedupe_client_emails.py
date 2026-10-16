from django.db import migrations


def dedupe_client_emails(apps, schema_editor):
    ClientEmail = apps.get_model('apps', 'ClientEmail')
    seen = set()
    duplicates = []
    for pk, email in ClientEmail.objects.order_by('id').values_list('pk', 'email'):
        key = email.strip().lower()
        if key in seen:
            duplicates.append(pk)
        seen.add(key)
    ClientEmail.objects.filter(pk__in=duplicates).delete()
    for subscriber in ClientEmail.objects.all():
        email = subscriber.email.strip().lower()
        if email != subscriber.email:
            subscriber.email = email
            subscriber.save(update_fields=['email'])


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0018_contactform_optional_fields'),
    ]

    operations = [
        migrations.RunPython(dedupe_client_emails, migrations.RunPython.noop),
    ]
