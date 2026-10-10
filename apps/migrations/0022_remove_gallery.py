from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0021_video_url'),
    ]

    operations = [
        migrations.DeleteModel(name='GalleryGroup'),
        migrations.DeleteModel(name='Gallery'),
    ]
