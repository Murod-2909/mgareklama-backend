from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from PIL import Image

from apps.models import Gallery, GalleryGroup, Project, ProjectPhoto
from apps.test_video import HOST, VideoTestCase, png_upload, upload

VALID = [
    'https://www.instagram.com/reel/C1a2B3c4D5e/',
    'https://instagram.com/reel/C1a2B3c4D5e',
    'https://www.instagram.com/p/C1a2B3c4D5e/?igsh=abc123',
    'https://www.instagram.com/reels/C1a2B3c4D5e/',
    'https://www.instagram.com/tv/C1a2B3c4D5e/',
    'https://www.instagram.com/mga.reklama/reel/C1a2B3c4D5e/',
    'http://www.instagram.com/p/C1a2B3c4D5e/',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://youtube.com/watch?v=dQw4w9WgXcQ&t=10s',
    'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://youtu.be/dQw4w9WgXcQ',
    'https://www.youtube.com/shorts/dQw4w9WgXcQ',
    'https://www.youtube.com/embed/dQw4w9WgXcQ',
    'https://www.youtube.com/live/dQw4w9WgXcQ?feature=share',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123&index=2',
    'https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ',
    'https://youtu.be/dQw4w9WgXcQ?si=abc123',
    'https://youtu.be/dQw4w9WgXcQ/',
    'https://youtu.be/a_B-c1D2e3F',
]
YOUTUBE_NOT_A_VIDEO = [
    'https://www.youtube.com/',
    'https://youtube.com',
    'https://www.youtube.com/@mgareklama',
    'https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv',
    'https://www.youtube.com/c/mgareklama',
    'https://www.youtube.com/user/mgareklama',
    'https://www.youtube.com/playlist?list=PLabc123def456',
    'https://www.youtube.com/feed/subscriptions',
    'https://www.youtube.com/results?search_query=mga',
    'https://www.youtube.com/watch',
    'https://www.youtube.com/watch?list=PLabc123def456',
    'https://www.youtube.com/watch?v=short',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQextra',
    'https://www.youtube.com/watch?v=dQw4w9Wg!cQ',
    'https://www.youtube.com/shorts/',
    'https://www.youtube.com/shorts/abc',
    'https://www.youtube.com/embed/',
    'https://www.youtube.com/live',
    'https://www.youtube.com/v/dQw4w9WgXcQ',
    'https://youtu.be/',
    'https://youtu.be/short',
    'https://youtu.be/dQw4w9WgXcQ/extra',
    'https://m.youtube.com/@mgareklama',
]
INVALID = [
    'https://vimeo.com/12345',
    'https://www.tiktok.com/@user/video/123',
    'https://facebook.com/watch?v=1',
    'https://instagram.com.evil.com/reel/C1a2B3c4D5e/',
    'https://evil.com/www.instagram.com/reel/C1a2B3c4D5e/',
    'https://www.instagram.com@evil.com/reel/C1a2B3c4D5e/',
    'https://notyoutube.com/watch?v=1',
    'https://www.instagram.com/',
    'https://www.instagram.com/mga.reklama/',
    'https://www.instagram.com/stories/user/123/',
    'https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ',
    'https://www.youtube.com@evil.com/watch?v=dQw4w9WgXcQ',
    'ftp://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'javascript:alert(1)',
    'not a url',
]


class VideoLinkValidationTests(VideoTestCase):
    def test_valid_links_are_accepted(self):
        for url in VALID:
            with self.subTest(url):
                Gallery(video_url=url).full_clean()

    def test_other_sites_and_tricks_are_rejected(self):
        for url in INVALID:
            with self.subTest(url), self.assertRaises(ValidationError):
                Gallery(video_url=url).full_clean()

    def test_youtube_channels_playlists_and_home_are_rejected(self):
        for url in YOUTUBE_NOT_A_VIDEO:
            with self.subTest(url), self.assertRaises(ValidationError) as ctx:
                Gallery(video_url=url).full_clean()
            self.assertIn('Enter a link to a specific YouTube video.', str(ctx.exception))

    def test_youtube_message_is_translated(self):
        for language, expected in (('uz', "YouTube'dagi aniq video havolasini kiriting"),
                                   ('ru', "Укажите ссылку на конкретное видео на YouTube")):
            with translation.override(language):
                try:
                    Gallery(video_url='https://www.youtube.com/@mgareklama').full_clean()
                except ValidationError as error:
                    text = str(error)
                else:
                    self.fail('ValidationError expected')
            self.assertIn(expected, text)

    def test_nothing_at_all_is_rejected_but_each_alone_is_fine(self):
        for model in (Gallery, GalleryGroup, ProjectPhoto):
            with self.subTest(model.__name__), self.assertRaises(ValidationError) as ctx:
                model().full_clean(exclude=['gallery', 'project'])
            self.assertIn('Upload an image or a video, or add a video link', str(ctx.exception))
        Gallery(image=png_upload()).full_clean()
        Gallery(video=upload(self.mp4)).full_clean()
        Gallery(video_url=VALID[0]).full_clean()

    def test_error_messages_are_translated(self):
        for language, expected in (('uz', "Faqat Instagram va YouTube havolalariga ruxsat beriladi"),
                                   ('ru', "Допустимы только ссылки на Instagram и YouTube"),
                                   ('en', "Only Instagram and YouTube links are allowed")):
            with translation.override(language):
                try:
                    Gallery(video_url='https://vimeo.com/1').full_clean()
                except ValidationError as error:
                    text = str(error)
                else:
                    self.fail('ValidationError expected')
            self.assertIn(expected, text)

    def test_file_and_link_together_is_allowed_and_file_wins(self):
        gallery = Gallery(video=upload(self.mp4), video_url=VALID[0])
        gallery.full_clean()
        gallery.save()
        self.assertEqual((gallery.media_type, gallery.duration), ('video', 5))
        self.assertTrue(gallery.video.name.endswith('.mp4'))
        self.assertEqual(gallery.video_url, VALID[0])


class VideoLinkApiTests(VideoTestCase):
    def api(self, url='/api/v1/images/'):
        return self.client.get(url, **HOST).json()

    def test_link_only_item(self):
        Gallery.objects.create(video_url=VALID[0])
        item = self.api()[0]
        self.assertEqual(list(item), ['id', 'media_type', 'image', 'thumbnail', 'video', 'video_url', 'duration',
                                      'same_images'])
        self.assertEqual((item['media_type'], item['video_url'], item['video'], item['duration']),
                         ('video', VALID[0], None, None))
        self.assertIsNone(item['image'])

    def test_link_with_poster(self):
        Gallery.objects.create(video_url=VALID[0], image=png_upload())
        item = self.api()[0]
        self.assertEqual(item['media_type'], 'video')
        self.assertTrue(item['image'].endswith('.webp') and item['thumbnail'].endswith('.webp'))

    def test_image_items_have_empty_link(self):
        Gallery.objects.create(image=png_upload())
        item = self.api()[0]
        self.assertEqual((item['media_type'], item['video_url'], item['video']), ('image', '', None))

    def test_same_images_expose_the_link(self):
        gallery = Gallery.objects.create(image=png_upload())
        GalleryGroup.objects.create(gallery=gallery, video_url=VALID[7])
        group = self.api()[0]['same_images'][0]
        self.assertEqual((group['media_type'], group['video_url']), ('video', VALID[7]))

    def test_removing_the_file_resets_duration(self):
        gallery = Gallery.objects.create(video=upload(self.mp4), video_url=VALID[0])
        self.assertEqual(gallery.duration, 5)
        gallery.video = None
        gallery.save()
        gallery.refresh_from_db()
        self.assertEqual((gallery.duration, gallery.media_type), (None, 'video'))
        gallery.video_url = ''
        gallery.save()
        self.assertEqual(Gallery.objects.get().media_type, 'image')

    def test_has_video_counts_links(self):
        def make(slug, **photo):
            project = Project.objects.create(slug=slug, cover=png_upload(), is_published=True)
            project.set_current_language('en')
            project.title = slug
            project.save()
            ProjectPhoto.objects.create(project=project, **photo)

        make('with-link', video_url=VALID[0])
        make('with-youtube', video_url=VALID[7], image=png_upload())
        make('images-only', image=png_upload())
        listing = {p['slug']: p for p in self.api('/api/v1/projects/?lang=en')}
        self.assertTrue(listing['with-link']['has_video'])
        self.assertTrue(listing['with-youtube']['has_video'])
        self.assertFalse(listing['images-only']['has_video'])
        detail = self.api('/api/v1/projects/with-link/?lang=en')
        self.assertTrue(detail['has_video'])
        self.assertEqual(detail['photos'][0]['video_url'], VALID[0])
        with CaptureQueriesContext(connection) as few:
            self.api('/api/v1/projects/?lang=en')
        for i in range(3):
            make(f'more-{i}', video_url=VALID[0])
        with self.assertNumQueries(len(few)):
            self.api('/api/v1/projects/?lang=en')


class VideoLinkAdminTests(VideoTestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin', 'a@a.uz', 'x'))

    def add_gallery(self, **fields):
        data = {'same_images-TOTAL_FORMS': '0', 'same_images-INITIAL_FORMS': '0', 'same_images-MIN_NUM_FORMS': '0',
                'same_images-MAX_NUM_FORMS': '1000', '_save': 'Save', **fields}
        return self.client.post('/admin/apps/gallery/add/', data, **HOST)

    def test_add_with_link_only(self):
        self.assertEqual(self.add_gallery(video_url=VALID[0]).status_code, 302)
        gallery = Gallery.objects.get()
        self.assertEqual((gallery.media_type, gallery.video_url), ('video', VALID[0]))

    def test_add_with_link_and_poster(self):
        self.assertEqual(self.add_gallery(video_url=VALID[0], image=png_upload()).status_code, 302)
        gallery = Gallery.objects.get()
        with Image.open(gallery.image.path) as im:
            self.assertEqual(im.format, 'WEBP')

    def test_bad_link_shows_error(self):
        response = self.add_gallery(video_url='https://vimeo.com/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Only Instagram and YouTube links are allowed', response.content.decode())
        self.assertEqual(Gallery.objects.count(), 0)

    def test_empty_form_error_mentions_link(self):
        self.assertIn('add a video link', self.add_gallery().content.decode())

    def test_inline_accepts_link(self):
        gallery = Gallery.objects.create(image=png_upload())
        response = self.client.post(f'/admin/apps/gallery/{gallery.pk}/change/', {
            'same_images-TOTAL_FORMS': '1', 'same_images-INITIAL_FORMS': '0', 'same_images-MIN_NUM_FORMS': '0',
            'same_images-MAX_NUM_FORMS': '1000', 'same_images-0-video_url': VALID[0], '_save': 'Save'}, **HOST)
        self.assertEqual(response.status_code, 302, response.content.decode()[:300])
        self.assertEqual(gallery.same_images.get().media_type, 'video')

    def test_form_and_preview_show_the_link(self):
        gallery = Gallery.objects.create(video_url=VALID[0])
        change = self.client.get(f'/admin/apps/gallery/{gallery.pk}/change/', **HOST).content.decode()
        self.assertIn('name="video_url"', change)
        self.assertIn('Instagram or YouTube link', change)
        listing = self.client.get('/admin/apps/gallery/', **HOST).content.decode()
        self.assertIn(f'href="{VALID[0]}"', listing)
