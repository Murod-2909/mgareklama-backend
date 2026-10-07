import re

from django.conf import settings
from django.utils.html import strip_tags
from rest_framework.serializers import EmailField, ValidationError, BooleanField, ModelSerializer, CharField, ImageField, SerializerMethodField

from apps.models import Gallery, SiteSetting, Partner, Service, ServiceWork, ContactForm, ClientEmail, GalleryGroup, \
    Project, ProjectPhoto


class GalleryGroupSerializer(ModelSerializer):
    class Meta:
        model = GalleryGroup
        fields = ['id', 'media_type', 'image', 'thumbnail', 'video', 'duration']

class GallerySerializer(ModelSerializer):
    same_images = GalleryGroupSerializer(many=True, read_only=True)

    class Meta:
        model = Gallery
        fields = ['id', 'media_type', 'image', 'thumbnail', 'video', 'duration', 'same_images']

class SiteSettingSerializer(ModelSerializer):
    class Meta:
        model = SiteSetting
        fields = '__all__'


class PartnerModelSerializer(ModelSerializer):
    class Meta:
        model = Partner
        fields = '__all__'


class ServiceWorkSerializer(ModelSerializer):
    class Meta:
        model = ServiceWork
        fields = 'id', 'image', 'thumbnail'


class ServiceModelSerializer(ModelSerializer):
    title = CharField(read_only=True)
    description = CharField(read_only=True)
    works = ServiceWorkSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = 'id', 'slug', 'title', 'description', 'image', 'thumbnail', 'works'


SCRIPT_OR_STYLE = re.compile(r'<(script|style)\b.*?</\1\s*>', re.IGNORECASE | re.DOTALL)


def clean_text(value, single_line=False):
    value = strip_tags(SCRIPT_OR_STYLE.sub('', value)).strip()
    return ' '.join(value.split()) if single_line else value


class ContactFormModelSerializers(ModelSerializer):
    message = CharField(min_length=1, max_length=3000)
    website = CharField(write_only=True, required=False, allow_blank=True)
    lang = CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ContactForm
        fields = 'id', 'name', 'email', 'phone', 'subject', 'message', 'website', 'lang'

    def _clean(self, value, single_line):
        cleaned = clean_text(value, single_line)
        if not cleaned and value.strip():
            raise ValidationError("This field may not contain only HTML.")
        return cleaned

    def validate_name(self, value):
        return self._clean(value, True)

    def validate_subject(self, value):
        return self._clean(value, True)

    def validate_message(self, value):
        return self._clean(value, False)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_lang(self, value):
        return value if value in dict(settings.LANGUAGES) else 'en'

    def create(self, validated_data):
        validated_data.pop('website', None)
        validated_data.pop('lang', None)
        return super().create(validated_data)


class ClientEmailModelSerializers(ModelSerializer):
    email = EmailField(max_length=100)

    class Meta:
        model = ClientEmail
        fields = 'id', 'email'

    def validate_email(self, value):
        return value.strip().lower()


class ProjectPhotoSerializer(ModelSerializer):
    class Meta:
        model = ProjectPhoto
        fields = 'id', 'media_type', 'image', 'thumbnail', 'video', 'duration'


class ProjectListSerializer(ModelSerializer):
    title = CharField(read_only=True)
    location = CharField(read_only=True)
    cover = ImageField(read_only=True)
    cover_thumbnail = ImageField(source='thumbnail', read_only=True)
    photos_count = SerializerMethodField()
    has_video = BooleanField(read_only=True)

    class Meta:
        model = Project
        fields = ('id', 'slug', 'title', 'location', 'year', 'category',
                  'cover', 'cover_thumbnail', 'photos_count', 'has_video')

    def get_photos_count(self, obj):
        return len(obj.photos.all())


class ProjectDetailSerializer(ProjectListSerializer):
    description = CharField(read_only=True)
    materials = CharField(read_only=True)
    photos = ProjectPhotoSerializer(many=True, read_only=True)

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + ('description', 'materials', 'photos')
