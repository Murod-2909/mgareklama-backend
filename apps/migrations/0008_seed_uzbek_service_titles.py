from django.db import migrations

UZBEK_TITLES_BY_ENGLISH_TITLE = {
    "UV Printing": "UV bosib chiqarish",
    "İnterior Printing": "Interyer bosib chiqarish",
    "Interior Printing": "Interyer bosib chiqarish",
    "Outdoor Printing": "Tashqi reklama bosib chiqarish",
    "Metal Laser Cutting Machine": "Metall lazer kesish stanogi",
    "Cnc Cutting": "CNC kesish",
    "Laser Plexiglass Machine": "Lazer pleksiglas stanogi",
    "Letter Bending Machine": "Harf bukish stanogi",
    "Laser Welding": "Lazer payvandlash",
    "Plotter Cutting": "Ploter kesish",
}


def add_uzbek_service_titles(apps, schema_editor):
    ServiceTranslation = apps.get_model('apps', 'ServiceTranslation')

    for english_title, uzbek_title in UZBEK_TITLES_BY_ENGLISH_TITLE.items():
        master_ids = ServiceTranslation.objects.filter(
            language_code='en', title=english_title,
        ).values_list('master_id', flat=True)

        for master_id in master_ids:
            ServiceTranslation.objects.update_or_create(
                master_id=master_id, language_code='uz',
                defaults={'title': uzbek_title, 'description': ''},
            )


def remove_uzbek_service_titles(apps, schema_editor):
    ServiceTranslation = apps.get_model('apps', 'ServiceTranslation')
    ServiceTranslation.objects.filter(
        language_code='uz', title__in=UZBEK_TITLES_BY_ENGLISH_TITLE.values(),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0007_servicetranslation_description'),
    ]

    operations = [
        migrations.RunPython(add_uzbek_service_titles, remove_uzbek_service_titles),
    ]
