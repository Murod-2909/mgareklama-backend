import os
import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile, File
from django.db.models import Model, ImageField, FileField, CharField, PositiveIntegerField, URLField
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageChops, ImageOps

from apps import video_utils

MAIN_MAX_SIDE = 1600
TRIM_PADDING = 0.04
MAIN_QUALITY = 80
THUMB_MAX_SIDE = 600
THUMB_QUALITY = 75


def _encode_webp(im, max_side, quality):
    im = im.copy()
    im.thumbnail((max_side, max_side), Image.LANCZOS)  # never enlarges
    buffer = BytesIO()
    im.save(buffer, format='WEBP', quality=quality, method=4)
    return buffer.getvalue()


def _content_bbox(im):
    if im.mode == 'RGBA':
        bbox = im.getchannel('A').point(lambda p: 255 if p > 10 else 0).getbbox()
        if bbox is None or bbox != (0, 0) + im.size:
            return bbox
    rgb = im.convert('RGB')
    background = Image.new('RGB', rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, background)
    return ImageChops.add(diff, diff, 2.0, -20).getbbox()


def trim_empty_borders(im):
    bbox = _content_bbox(im)
    if not bbox or bbox == (0, 0) + im.size:
        return im
    cropped = im.crop(bbox)
    pad = round(max(cropped.size) * TRIM_PADDING)
    if im.mode == 'RGBA':
        fill = (0, 0, 0, 0)
    else:
        fill = im.getpixel((0, 0))
    canvas = Image.new(im.mode, (cropped.width + 2 * pad, cropped.height + 2 * pad), fill)
    canvas.paste(cropped, (pad, pad))
    return canvas


def build_variants(fileobj, main_max_side=MAIN_MAX_SIDE, trim=False):
    with Image.open(fileobj) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ('P', 'LA', 'PA'):
            im = im.convert('RGBA')
        elif im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        if trim:
            im = trim_empty_borders(im)
        main = _encode_webp(im, main_max_side, MAIN_QUALITY)
        thumb = _encode_webp(im, THUMB_MAX_SIDE, THUMB_QUALITY)
    return main, thumb


def webp_name(name):
    return os.path.splitext(os.path.basename(name))[0] + '.webp'


class OptimizedImageModel(Model):
    thumbnail = ImageField(upload_to='thumbs/%Y/%m/%d', blank=True, editable=False)

    image_field = 'image'
    main_max_side = MAIN_MAX_SIDE
    trim_logo = False

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
            main, thumb = build_variants(source.file, self.main_max_side, trim=self.trim_logo)
            self.apply_variants(main, thumb, source.name)
        super().save(*args, **kwargs)


class OptimizedMediaModel(OptimizedImageModel):
    MEDIA_TYPES = [('image', 'Image'), ('video', 'Video')]

    video = FileField(upload_to='videos/%Y/%m/%d', blank=True, null=True, verbose_name=_("Video"),
                      help_text=_("MP4/MOV/WEBM, up to 120 seconds, up to 100 MB. The poster is created automatically."))
    video_url = URLField(max_length=300, blank=True, verbose_name=_("Video link"),
                         help_text=_("Instagram or YouTube link (for example https://www.instagram.com/reel/XXXX/). "
                                     "For Instagram also upload a poster image. "
                                     "If a video file is uploaded too, the file takes priority."))
    media_type = CharField(max_length=5, choices=MEDIA_TYPES, default='image', editable=False, db_index=True)
    duration = PositiveIntegerField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def _is_new_video(self):
        return bool(self.video) and not self.video._committed

    def clean(self):
        super().clean()
        if not self.image and not self.video and not self.video_url:
            raise ValidationError(_("Upload an image or a video, or add a video link."))
        if self.video_url:
            video_utils.validate_video_url(self.video_url)
        if self._is_new_video():
            with tempfile.TemporaryDirectory() as directory:
                video_utils.validate_video_upload(self.video, directory)

    def _process_new_video(self):
        with tempfile.TemporaryDirectory() as directory:
            duration = video_utils.validate_video_upload(self.video, directory)
            source = os.path.join(directory, 'source' + os.path.splitext(self.video.name)[1].lower())
            target = os.path.join(directory, 'video.mp4')
            video_utils.transcode(source, target)

            name = os.path.splitext(os.path.basename(self.video.name))[0] + '.mp4'
            with open(target, 'rb') as f:
                self.video.save(name, File(f), save=False)
            self.duration = round(duration)

            custom_poster = self.image and not self.image._committed
            if not custom_poster:
                poster = os.path.join(directory, 'poster.png')
                video_utils.extract_poster(target, poster, duration)
                with open(poster, 'rb') as f:
                    main, thumb = build_variants(f, self.main_max_side, trim=self.trim_logo)
                self.apply_variants(main, thumb, name)

    def save(self, *args, **kwargs):
        old_video = None
        if self.pk:
            old_video = type(self).objects.filter(pk=self.pk).values_list('video', flat=True).first()
        if self._is_new_video():
            self._process_new_video()
        self.media_type = 'video' if (self.video or self.video_url) else 'image'
        if not self.video:
            self.duration = None
        super().save(*args, **kwargs)
        if old_video and old_video != self.video.name:
            self.video.storage.delete(old_video)
