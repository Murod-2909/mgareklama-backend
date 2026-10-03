import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.db.models import Model, ImageField
from PIL import Image, ImageOps

MAIN_MAX_SIDE = 1600
MAIN_QUALITY = 80
THUMB_MAX_SIDE = 600
THUMB_QUALITY = 75


def _encode_webp(im, max_side, quality):
    im = im.copy()
    im.thumbnail((max_side, max_side), Image.LANCZOS)  # never enlarges
    buffer = BytesIO()
    im.save(buffer, format='WEBP', quality=quality, method=4)
    return buffer.getvalue()


def build_variants(fileobj, main_max_side=MAIN_MAX_SIDE):
    with Image.open(fileobj) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ('P', 'LA', 'PA'):
            im = im.convert('RGBA')
        elif im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        main = _encode_webp(im, main_max_side, MAIN_QUALITY)
        thumb = _encode_webp(im, THUMB_MAX_SIDE, THUMB_QUALITY)
    return main, thumb


def webp_name(name):
    return os.path.splitext(os.path.basename(name))[0] + '.webp'


class OptimizedImageModel(Model):
    thumbnail = ImageField(upload_to='thumbs/%Y/%m/%d', blank=True, editable=False)

    image_field = 'image'
    main_max_side = MAIN_MAX_SIDE

    class Meta:
        abstract = True

    @property
    def source_image(self):
        return getattr(self, self.image_field)

    def apply_variants(self, main, thumb, source_name):
        name = webp_name(source_name)
        self.source_image.save(name, ContentFile(main), save=False)
        self.thumbnail.save(name, ContentFile(thumb), save=False)

    def save(self, *args, **kwargs):
        # FieldFile._committed is False only for a freshly assigned/uploaded file
        source = self.source_image
        if source and not source._committed:
            source.file.seek(0)
            main, thumb = build_variants(source.file, self.main_max_side)
            self.apply_variants(main, thumb, source.name)
        super().save(*args, **kwargs)
