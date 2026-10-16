from django.db import migrations
from django.utils.text import slugify


def lowercase_slugs(apps, schema_editor):
    Project = apps.get_model('apps', 'Project')
    taken = set(Project.objects.values_list('slug', flat=True))
    for project in Project.objects.order_by('id'):
        new = slugify(project.slug)
        if not new or new == project.slug:
            continue
        base, n = new, 2
        while new in taken and new != project.slug:
            new, n = f"{base}-{n}", n + 1
        taken.discard(project.slug)
        taken.add(new)
        project.slug = new
        project.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0012_project_projectphoto_projecttranslation'),
    ]

    operations = [
        migrations.RunPython(lowercase_slugs, migrations.RunPython.noop),
    ]
