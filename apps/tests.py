import importlib
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image, ImageDraw

from apps.image_utils import build_variants, trim_empty_borders
from apps.models import Partner, Service

TEMP_MEDIA = tempfile.mkdtemp()


def png_upload(name, size=(800, 600), color=(10, 120, 200)):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), 'image/png')


class TrimEmptyBordersTests(TestCase):
    def logo(self, mode, background):
        im = Image.new(mode, (1600, 1131), background)
        ImageDraw.Draw(im).rectangle((700, 500, 900, 560), fill=(20, 30, 200) + ((255,) if mode == 'RGBA' else ()))
        return im

    def test_trims_rgb_background(self):
        self.assertEqual(trim_empty_borders(self.logo('RGB', 'white')).size, (217, 77))

    def test_trims_transparent_rgba(self):
        trimmed = trim_empty_borders(self.logo('RGBA', (0, 0, 0, 0)))
        self.assertEqual(trimmed.size, (217, 77))
        self.assertEqual(trimmed.getpixel((0, 0))[3], 0)

    def test_trims_opaque_rgba_by_color(self):
        self.assertEqual(trim_empty_borders(self.logo('RGBA', (255, 255, 255, 255))).size, (217, 77))

    def test_blank_images_are_left_alone(self):
        self.assertEqual(trim_empty_borders(Image.new('RGB', (300, 200), 'white')).size, (300, 200))
        self.assertEqual(trim_empty_borders(Image.new('RGBA', (300, 200), (0, 0, 0, 0))).size, (300, 200))

    def test_build_variants_trims_only_when_asked(self):
        buffer = io.BytesIO()
        self.logo('RGB', 'white').save(buffer, 'PNG')
        for trim, expected in ((False, (1600, 1131)), (True, (217, 77))):
            buffer.seek(0)
            main, _ = build_variants(buffer, trim=trim)
            self.assertEqual(Image.open(io.BytesIO(main)).size, expected)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ServiceTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def test_slug_is_lowercased_and_blank_becomes_null(self):
        self.assertEqual(Service.objects.create(slug='  Laser WELDING ').slug, 'laser-welding')
        first, second = Service.objects.create(slug=''), Service.objects.create()
        self.assertIsNone(first.slug)
        self.assertIsNone(second.slug)

    def test_uploaded_icon_is_optimized_with_thumbnail(self):
        service = Service.objects.create(image=png_upload('icon.png', (2400, 2400)))
        self.assertTrue(service.image.name.endswith('.webp'))
        self.assertTrue(service.thumbnail.name.endswith('.webp'))
        with Image.open(service.image.path) as im:
            self.assertEqual(im.size, (1200, 1200))

    def test_service_without_image_saves(self):
        self.assertFalse(Service.objects.create().thumbnail)

    def test_partner_logo_is_trimmed(self):
        logo = Image.new('RGB', (1600, 1131), 'white')
        ImageDraw.Draw(logo).rectangle((700, 500, 900, 560), fill=(20, 30, 200))
        buffer = io.BytesIO()
        logo.save(buffer, 'PNG')
        partner = Partner.objects.create(image=SimpleUploadedFile('logo.png', buffer.getvalue(), 'image/png'))
        with Image.open(partner.image.path) as im:
            self.assertEqual(im.size, (217, 77))

    def test_api_keeps_old_keys_and_adds_new_ones(self):
        service = Service.objects.create(slug='uv-printing', image=png_upload('uv.png'))
        service.set_current_language('en')
        service.title = 'UV Printing'
        service.save()
        data = self.client.get('/api/v1/services/?lang=en', HTTP_HOST='127.0.0.1').json()[0]
        self.assertEqual(list(data), ['id', 'slug', 'title', 'description', 'image', 'thumbnail', 'works'])
        self.assertEqual(data['slug'], 'uv-printing')


class ServiceSlugMigrationTests(TestCase):
    def test_slug_matches_image_file_names(self):
        migration = importlib.import_module('apps.migrations.0015_seed_service_slugs')
        cases = {
            'services-icon/2025/07/19/UV_PECHAT.png': 'uv-printing',
            'services-icon/2025/07/19/UV_PECHAT_aB3dE9x.png': 'uv-printing',
            'services-icon/2025/07/19/ECO_PECHAT.png': 'interior-printing',
            'services-icon/2025/07/19/SHROKAFORMATNI_PECHAT.png': 'outdoor-printing',
            'services-icon/2025/07/19/LAZER_hlUVlLl.png': 'metal-laser-cutting-machine',
            'services-icon/2025/07/19/CNC_rover.png': 'cnc-cutting',
            'services-icon/2025/07/19/laser_l.png': 'laser-plexiglass-machine',
            'services-icon/2025/07/19/laser.png': 'letter-bending-machine',
            'services-icon/2025/07/19/juyuan.png': 'laser-welding',
            'services-icon/2025/07/19/PLOTER_RESKA.png': 'plotter-cutting',
            'services-icon/2025/07/19/something_else.png': None,
        }
        for name, slug in cases.items():
            self.assertEqual(migration.slug_for_image(name), slug, name)
