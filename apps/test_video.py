import atexit
import io
import json
import os
import shutil
import subprocess
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from PIL import Image

from apps.models import Gallery, GalleryGroup, Project, ProjectPhoto, Service, ServiceWork

TEMP_MEDIA = tempfile.mkdtemp()
SAMPLES = tempfile.mkdtemp()
atexit.register(shutil.rmtree, TEMP_MEDIA, ignore_errors=True)
atexit.register(shutil.rmtree, SAMPLES, ignore_errors=True)
HOST = {'HTTP_HOST': '127.0.0.1'}


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *args], check=True)


def make_sample(name, seconds, size, rate=25, audio=True):
    path = os.path.join(SAMPLES, name)
    if not os.path.exists(path):
        inputs = ['-f', 'lavfi', '-i', f'testsrc=duration={seconds}:size={size}:rate={rate}']
        if audio:
            inputs += ['-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}']
        ffmpeg(*inputs, '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
               *(['-c:a', 'aac'] if audio else []), path)
    return path


def upload(path, name=None):
    with open(path, 'rb') as f:
        return SimpleUploadedFile(name or os.path.basename(path), f.read())


def png_upload(name='poster.png', size=(640, 360), color=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), 'image/png')


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name,width,height,codec_type',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)['streams']


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class VideoTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mp4 = make_sample('clip.mp4', 5, '640x360')
        cls.vertical = make_sample('vertical.mov', 3, '1080x1920', rate=10)

    def admin_client(self):
        user = User.objects.create_superuser('admin', 'a@a.uz', 'x')
        self.client.force_login(user)
        return self.client

    def add_gallery_via_admin(self, **files):
        data = {'same_images-TOTAL_FORMS': '0', 'same_images-INITIAL_FORMS': '0',
                'same_images-MIN_NUM_FORMS': '0', 'same_images-MAX_NUM_FORMS': '1000', '_save': 'Save', **files}
        return self.admin_client().post('/admin/apps/gallery/add/', data, **HOST)

    def api_images(self):
        return self.client.get('/api/v1/images/', **HOST).json()


class AdminVideoUploadTests(VideoTestCase):
    def test_mp4_upload_via_admin(self):
        response = self.add_gallery_via_admin(video=upload(self.mp4))
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['errors'])
        item = self.api_images()[0]
        self.assertEqual(item['media_type'], 'video')
        self.assertTrue(item['video'].startswith('http://127.0.0.1') and item['video'].endswith('.mp4'))
        self.assertTrue(item['image'].endswith('.webp') and item['thumbnail'].endswith('.webp'))
        self.assertEqual(item['duration'], 5)
        self.assertEqual(list(item), ['id', 'media_type', 'image', 'thumbnail', 'video', 'video_url', 'duration', 'same_images'])
        gallery = Gallery.objects.get()
        with open(gallery.video.path, 'rb') as f:
            head = f.read(200_000)
        self.assertLess(head.find(b'moov'), head.find(b'mdat'), 'moov must come first (faststart)')
        codecs = {s['codec_type']: s['codec_name'] for s in probe(gallery.video.path)}
        self.assertEqual(codecs, {'video': 'h264', 'audio': 'aac'})
        with Image.open(gallery.thumbnail.path) as im:
            self.assertLessEqual(max(im.size), 600)

    def test_vertical_mov_long_side_is_capped_at_1280(self):
        self.assertEqual(self.add_gallery_via_admin(video=upload(self.vertical)).status_code, 302)
        gallery = Gallery.objects.get()
        stream = [s for s in probe(gallery.video.path) if s['codec_type'] == 'video'][0]
        self.assertEqual((stream['width'], stream['height']), (720, 1280))
        self.assertLessEqual(max(stream['width'], stream['height']), 1280)
        self.assertTrue(gallery.video.name.endswith('.mp4'))
        self.assertEqual(self.api_images()[0]['duration'], 3)

    def test_wide_video_is_scaled_to_1280(self):
        wide = make_sample('wide.mp4', 1, '1920x1080', rate=5, audio=False)
        self.assertEqual(self.add_gallery_via_admin(video=upload(wide)).status_code, 302)
        stream = probe(Gallery.objects.get().video.path)[0]
        self.assertEqual((stream['width'], stream['height']), (1280, 720))

    def test_small_vertical_video_is_not_upscaled(self):
        small = make_sample('small_vertical.mp4', 1, '360x640', rate=5, audio=False)
        self.assertEqual(self.add_gallery_via_admin(video=upload(small)).status_code, 302)
        stream = probe(Gallery.objects.get().video.path)[0]
        self.assertEqual((stream['width'], stream['height']), (360, 640))

    def test_own_poster_is_used(self):
        self.assertEqual(self.add_gallery_via_admin(video=upload(self.mp4), image=png_upload()).status_code, 302)
        gallery = Gallery.objects.get()
        self.assertEqual(gallery.media_type, 'video')
        with Image.open(gallery.image.path) as im:
            r, g, b = im.convert('RGB').getpixel((10, 10))
        self.assertGreater(r, 150)
        self.assertLess(g, 80)

    def test_image_only_works_as_before(self):
        self.assertEqual(self.add_gallery_via_admin(image=png_upload(size=(2400, 1600))).status_code, 302)
        item = self.api_images()[0]
        self.assertEqual((item['media_type'], item['video'], item['duration']), ('image', None, None))
        self.assertTrue(item['image'].endswith('.webp') and item['thumbnail'].endswith('.webp'))

    def test_empty_form_shows_error(self):
        response = self.add_gallery_via_admin()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Upload an image or a video, or add a video link', response.content.decode())
        self.assertEqual(Gallery.objects.count(), 0)

    def test_error_message_is_translated(self):
        for language, expected in (('uz', "Rasm yoki video yuklang, yoki video havolasini kiriting"),
                                   ('ru', "Загрузите изображение или видео, либо укажите ссылку"),
                                   ('en', "Upload an image or a video, or add a video link")):
            with translation.override(language):
                try:
                    Gallery().full_clean()
                except ValidationError as error:
                    text = str(error)
                else:
                    self.fail('ValidationError expected')
            self.assertIn(expected, text)

    def test_inline_video_in_gallery_group_and_project_photo(self):
        gallery = Gallery.objects.create(image=png_upload())
        group = GalleryGroup(gallery=gallery, video=upload(self.mp4))
        group.full_clean()
        group.save()
        self.assertEqual((group.media_type, group.duration), ('video', 5))
        project = Project.objects.create(cover=png_upload(), is_published=True)
        photo = ProjectPhoto(project=project, video=upload(self.mp4))
        photo.full_clean()
        photo.save()
        self.assertEqual((photo.media_type, photo.duration), ('video', 5))
        item = self.api_images()[0]['same_images'][0]
        self.assertEqual(item['media_type'], 'video')


class ValidationTests(VideoTestCase):
    def test_rejected_videos(self):
        long_video = make_sample('long.mp4', 180, '160x90', rate=5, audio=False)
        cases = {
            'too long': (upload(long_video), 'too long'),
            'too large': (SimpleUploadedFile('big.mp4', b'\0' * (130 * 1024 * 1024)), 'too large'),
            'bad extension': (SimpleUploadedFile('clip.avi', b'data'), 'Unsupported'),
            'not a video': (SimpleUploadedFile('fake.mp4', b'this is not a video'), 'could not be processed'),
        }
        for label, (file, message) in cases.items():
            with self.subTest(label):
                with self.assertRaises(ValidationError) as ctx:
                    Gallery(video=file).full_clean()
                self.assertIn(message, str(ctx.exception))
        self.assertEqual(Gallery.objects.count(), 0)

    def test_missing_ffmpeg_gives_clear_error(self):
        with mock.patch('apps.video_utils.shutil.which', return_value=None):
            with self.assertRaises(ValidationError) as ctx:
                Gallery(video=upload(self.mp4)).full_clean()
        self.assertIn('ffmpeg is not installed', str(ctx.exception))

    def test_image_only_and_video_only_are_valid(self):
        Gallery(image=png_upload()).full_clean()
        Gallery(video=upload(self.mp4)).full_clean()


class FileCleanupTests(VideoTestCase):
    def test_replacing_and_deleting_removes_video_files(self):
        gallery = Gallery(video=upload(self.mp4))
        gallery.save()
        first = gallery.video.path
        self.assertTrue(os.path.exists(first))
        gallery.video = upload(self.vertical, 'other.mov')
        gallery.save()
        self.assertFalse(os.path.exists(first), 'old video must be deleted on replace')
        second = gallery.video.path
        self.assertTrue(os.path.exists(second))
        gallery.delete()
        self.assertFalse(os.path.exists(second), 'video must be deleted with the record')

    def test_project_delete_cascades_to_video_files(self):
        project = Project.objects.create(cover=png_upload())
        photo = ProjectPhoto.objects.create(project=project, video=upload(self.mp4))
        path = photo.video.path
        project.delete()
        self.assertFalse(os.path.exists(path))

    def test_optimize_images_command_keeps_videos(self):
        from django.core.management import call_command
        gallery = Gallery.objects.create(video=upload(self.mp4))
        call_command('optimize_images', stdout=io.StringIO())
        self.assertTrue(os.path.exists(Gallery.objects.get(pk=gallery.pk).video.path))
        self.assertTrue(os.path.exists(gallery.image.path))


class ProjectApiTests(VideoTestCase):
    def make_project(self, slug, with_video):
        project = Project.objects.create(slug=slug, cover=png_upload(), is_published=True)
        project.set_current_language('en')
        project.title = slug
        project.save()
        ProjectPhoto.objects.create(project=project, image=png_upload())
        if with_video:
            ProjectPhoto.objects.create(project=project, video=upload(self.mp4))
        return project

    def get_list(self):
        return self.client.get('/api/v1/projects/?lang=en', **HOST).json()

    def test_has_video_and_photos_count(self):
        self.make_project('with-video', True)
        self.make_project('only-images', False)
        data = {p['slug']: p for p in self.get_list()}
        self.assertTrue(data['with-video']['has_video'])
        self.assertFalse(data['only-images']['has_video'])
        self.assertEqual(data['with-video']['photos_count'], 2)
        detail = self.client.get('/api/v1/projects/with-video/?lang=en', **HOST).json()
        self.assertTrue(detail['has_video'])
        self.assertEqual([p['media_type'] for p in detail['photos']], ['image', 'video'])
        self.assertEqual(list(detail['photos'][1]), ['id', 'media_type', 'image', 'thumbnail', 'video', 'video_url', 'duration'])
        self.assertEqual(detail['photos'][1]['duration'], 5)

    def test_query_count_does_not_grow(self):
        self.make_project('one', True)
        with CaptureQueriesContext(connection) as baseline:
            self.get_list()
        for i in range(4):
            self.make_project(f'more-{i}', i % 2 == 0)
        with self.assertNumQueries(len(baseline)):
            self.assertEqual(len(self.get_list()), 5)


class ServiceWorkUnchangedTests(VideoTestCase):
    def test_service_works_stay_image_only(self):
        service = Service.objects.create()
        service.set_current_language('en')
        service.title = 'S'
        service.save()
        ServiceWork.objects.create(service=service, image=png_upload())
        work = self.client.get('/api/v1/services/?lang=en', **HOST).json()[0]['works'][0]
        self.assertEqual(list(work), ['id', 'image', 'thumbnail'])
        self.assertFalse(hasattr(ServiceWork, 'video'))
