from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from PIL import Image

from apps.models import Project, ProjectPhoto
from apps.test_video import HOST, PHOTO_KEYS, VideoTestCase, png_upload, upload

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


def check(**fields):
    ProjectPhoto(**fields).full_clean(exclude=['project'])


class VideoLinkValidationTests(VideoTestCase):
    def test_valid_links_are_accepted(self):
        for url in VALID:
            with self.subTest(url):
                check(video_url=url)

    def test_other_sites_and_tricks_are_rejected(self):
        for url in INVALID:
            with self.subTest(url), self.assertRaises(ValidationError):
                check(video_url=url)

    def test_youtube_channels_playlists_and_home_are_rejected(self):
        for url in YOUTUBE_NOT_A_VIDEO:
            with self.subTest(url), self.assertRaises(ValidationError) as ctx:
                check(video_url=url)
            self.assertIn('Enter a link to a specific YouTube video.', str(ctx.exception))

    def test_youtube_message_is_translated(self):
        for language, expected in (('uz', "YouTube'dagi aniq video havolasini kiriting"),
                                   ('ru', "Укажите ссылку на конкретное видео на YouTube")):
            with translation.override(language):
                try:
                    check(video_url='https://www.youtube.com/@mgareklama')
                except ValidationError as error:
                    text = str(error)
                else:
                    self.fail('ValidationError expected')
            self.assertIn(expected, text)

    def test_nothing_at_all_is_rejected_but_each_alone_is_fine(self):
        with self.assertRaises(ValidationError) as ctx:
            check()
        self.assertIn('Upload an image or a video, or add a video link', str(ctx.exception))
        check(image=png_upload())
        check(video=upload(self.mp4))
        check(video_url=VALID[0])

    def test_error_messages_are_translated(self):
        for language, expected in (('uz', "Faqat Instagram va YouTube havolalariga ruxsat beriladi"),
                                   ('ru', "Допустимы только ссылки на Instagram и YouTube"),
                                   ('en', "Only Instagram and YouTube links are allowed")):
            with translation.override(language):
                try:
                    check(video_url='https://vimeo.com/1')
                except ValidationError as error:
                    text = str(error)
                else:
                    self.fail('ValidationError expected')
            self.assertIn(expected, text)

    def test_file_and_link_together_is_allowed_and_file_wins(self):
        photo = self.new_photo(video=upload(self.mp4), video_url=VALID[0])
        photo.full_clean()
        photo.save()
        self.assertEqual((photo.media_type, photo.duration), ('video', 5))
        self.assertTrue(photo.video.name.endswith('.mp4'))
        self.assertEqual(photo.video_url, VALID[0])


class VideoLinkApiTests(VideoTestCase):
    def api(self, url):
        return self.client.get(url, **HOST).json()

    def test_link_only_item(self):
        self.new_photo(video_url=VALID[0]).save()
        item = self.api_photos('holder')[0]
        self.assertEqual(list(item), PHOTO_KEYS)
        self.assertEqual((item['media_type'], item['video_url'], item['video'], item['duration']),
                         ('video', VALID[0], None, None))
        self.assertIsNone(item['image'])

    def test_link_with_poster(self):
        self.new_photo(video_url=VALID[0], image=png_upload()).save()
        item = self.api_photos('holder')[0]
        self.assertEqual(item['media_type'], 'video')
        self.assertTrue(item['image'].endswith('.webp') and item['thumbnail'].endswith('.webp'))

    def test_image_items_have_empty_link(self):
        self.new_photo(image=png_upload()).save()
        item = self.api_photos('holder')[0]
        self.assertEqual((item['media_type'], item['video_url'], item['video']), ('image', '', None))

    def test_removing_the_file_resets_duration(self):
        photo = self.new_photo(video=upload(self.mp4), video_url=VALID[0])
        photo.save()
        self.assertEqual(photo.duration, 5)
        photo.video = None
        photo.save()
        photo.refresh_from_db()
        self.assertEqual((photo.duration, photo.media_type), (None, 'video'))
        photo.video_url = ''
        photo.save()
        self.assertEqual(ProjectPhoto.objects.get().media_type, 'image')

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
    def test_add_with_link_only(self):
        self.assertEqual(self.add_photo_via_admin(video_url=VALID[0]).status_code, 302)
        photo = ProjectPhoto.objects.get()
        self.assertEqual((photo.media_type, photo.video_url), ('video', VALID[0]))
        self.assertEqual(self.api_photos()[0]['video_url'], VALID[0])

    def test_add_with_link_and_poster(self):
        self.assertEqual(self.add_photo_via_admin(video_url=VALID[0], image=png_upload()).status_code, 302)
        with Image.open(ProjectPhoto.objects.get().image.path) as im:
            self.assertEqual(im.format, 'WEBP')

    def test_bad_link_shows_error(self):
        response = self.add_photo_via_admin(video_url='https://vimeo.com/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Only Instagram and YouTube links are allowed', response.content.decode())
        self.assertEqual(ProjectPhoto.objects.count(), 0)

    def test_empty_photo_error_mentions_link(self):
        self.assertIn('add a video link', self.add_photo_via_admin(order='1').content.decode())

    def test_project_form_shows_the_link_field_and_preview(self):
        self.add_photo_via_admin(video_url=VALID[0])
        project = Project.objects.get()
        change = self.client.get(f'/admin/apps/project/{project.pk}/change/?language=en', **HOST).content.decode()
        self.assertIn('name="photos-0-video_url"', change)
        self.assertIn('name="photos-0-video"', change)
        self.assertIn('name="photos-0-image"', change)
        self.assertIn('Instagram or YouTube link', change)
        self.assertIn(f'href="{VALID[0]}"', change)
