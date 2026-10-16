import os
import re

from django.db import migrations

SLUGS_BY_IMAGE_STEM = {
    'uv_pechat': 'uv-printing',
    'eco_pechat': 'interior-printing',
    'shrokaformatni_pechat': 'outdoor-printing',
    'lazer_hluvlll': 'metal-laser-cutting-machine',
    'lazer': 'metal-laser-cutting-machine',
    'cnc_rover': 'cnc-cutting',
    'laser_l': 'laser-plexiglass-machine',
    'laser': 'letter-bending-machine',
    'juyuan': 'laser-welding',
    'ploter_reska': 'plotter-cutting',
}
RANDOM_SUFFIX = re.compile(r'_[a-z0-9]{7}$')


def slug_for_image(name):
    stem = os.path.splitext(os.path.basename(name))[0].lower()
    if stem in SLUGS_BY_IMAGE_STEM:
        return SLUGS_BY_IMAGE_STEM[stem]
    return SLUGS_BY_IMAGE_STEM.get(RANDOM_SUFFIX.sub('', stem))


def set_service_slugs(apps, schema_editor):
    Service = apps.get_model('apps', 'Service')
    taken = set(Service.objects.exclude(slug__isnull=True).values_list('slug', flat=True))
    for service in Service.objects.filter(slug__isnull=True).exclude(image='').exclude(image__isnull=True):
        slug = slug_for_image(service.image.name)
        if slug and slug not in taken:
            service.slug = slug
            service.save(update_fields=['slug'])
            taken.add(slug)


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0014_service_slug_service_thumbnail'),
    ]

    operations = [
        migrations.RunPython(set_service_slugs, migrations.RunPython.noop),
    ]
