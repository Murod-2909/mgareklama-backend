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


class FixServiceTitlesMigrationTests(TestCase):
    def make_service(self, slug, **titles):
        service = Service.objects.create(slug=slug)
        for language, title in titles.items():
            service.set_current_language(language)
            service.title = title
            service.save()
        return service

    def titles(self, lang):
        return {s['slug']: s['title'] for s in self.client.get(f'/api/v1/services/?lang={lang}', HTTP_HOST='127.0.0.1').json()}

    def test_wrong_titles_are_fixed_and_custom_ones_kept(self):
        from django.apps import apps
        migration = importlib.import_module('apps.migrations.0017_fix_service_titles')
        self.make_service('interior-printing', en='İnterior Printing', ru='Внутренняя печать', uz='Interyer bosib chiqarish')
        self.make_service('cnc-cutting', en='Cnc Cutting', ru='ЧПУ резка')
        self.make_service('laser-plexiglass-machine', en='Laser Plexiglass Machine',
                          ru='Лазерный сварочный аппарат для оргстекла', uz='Lazer pleksiglas stanogi')
        self.make_service('plotter-cutting', en='Plotter Cutting', ru='Плоттер реска')
        self.make_service('uv-printing', en='UV Printing', ru='Своё название')
        self.make_service('metal-laser-cutting-machine', en='Metal Laser Cutting Machine')

        migration.fix_service_titles(apps, None)
        migration.fix_service_titles(apps, None)  # idempotent

        en, ru, uz = self.titles('en'), self.titles('ru'), self.titles('uz')
        self.assertEqual(en['interior-printing'], 'Interior Printing')
        self.assertEqual(en['cnc-cutting'], 'CNC Cutting')
        self.assertEqual(en['metal-laser-cutting-machine'], 'Metal Laser Cutting Machine')
        self.assertEqual(ru['laser-plexiglass-machine'], 'Лазерный станок для оргстекла')
        self.assertEqual(ru['plotter-cutting'], 'Плоттерная резка')
        self.assertEqual(ru['uv-printing'], 'Своё название')
        self.assertEqual(ru['interior-printing'], 'Внутренняя печать')
        self.assertEqual(uz['interior-printing'], 'Interyer bosib chiqarish')

    def test_value_changed_by_admin_is_not_overwritten(self):
        from django.apps import apps
        migration = importlib.import_module('apps.migrations.0017_fix_service_titles')
        self.make_service('cnc-cutting', en='CNC cutting (custom)')
        migration.fix_service_titles(apps, None)
        self.assertEqual(self.titles('en')['cnc-cutting'], 'CNC cutting (custom)')


class GalleryRemovedTests(TestCase):
    def test_images_endpoint_is_gone_and_others_still_work(self):
        host = {'HTTP_HOST': '127.0.0.1'}
        self.assertEqual(self.client.get('/api/v1/images/', **host).status_code, 404)
        for url in ('/api/v1/projects/?lang=en', '/api/v1/services/?lang=en', '/api/v1/partners/'):
            self.assertEqual(self.client.get(url, **host).status_code, 200, url)

    def test_admin_has_no_gallery_but_keeps_projects(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.uz', 'x'))
        host = {'HTTP_HOST': '127.0.0.1'}
        self.assertEqual(self.client.get('/admin/apps/gallery/', **host).status_code, 404)
        self.assertEqual(self.client.get('/admin/apps/gallerygroup/', **host).status_code, 404)
        index = self.client.get('/admin/', **host).content.decode()
        self.assertNotIn('/admin/apps/gallery', index)
        self.assertIn('/admin/apps/project/', index)

    def test_models_are_removed(self):
        from django.apps import apps as django_apps
        names = {model.__name__ for model in django_apps.get_app_config('apps').get_models()}
        self.assertFalse({'Gallery', 'GalleryGroup'} & names)
        self.assertIn('ProjectPhoto', names)
