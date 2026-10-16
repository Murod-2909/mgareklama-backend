from django.db import migrations

# (slug, language, current wrong value, correct value); only replaced when the stored value still matches
FIXES = [
    ('interior-printing', 'en', 'İnterior Printing', 'Interior Printing'),
    ('cnc-cutting', 'en', 'Cnc Cutting', 'CNC Cutting'),
    ('laser-plexiglass-machine', 'ru', 'Лазерный сварочный аппарат для оргстекла', 'Лазерный станок для оргстекла'),
    ('plotter-cutting', 'ru', 'Плоттер реска', 'Плоттерная резка'),
]


def fix_service_titles(apps, schema_editor):
    ServiceTranslation = apps.get_model('apps', 'ServiceTranslation')
    for slug, language, wrong, correct in FIXES:
        ServiceTranslation.objects.filter(
            master__slug=slug, language_code=language, title=wrong,
        ).update(title=correct)


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0016_gallery_duration_gallery_media_type_gallery_video_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_service_titles, migrations.RunPython.noop),
    ]
