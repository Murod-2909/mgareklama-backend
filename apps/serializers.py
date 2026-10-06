from rest_framework.serializers import ModelSerializer, CharField, ImageField, SerializerMethodField

from apps.models import Gallery, SiteSetting, Partner, Service, ServiceWork, ContactForm, ClientEmail, GalleryGroup, \
    Project, ProjectPhoto


class GalleryGroupSerializer(ModelSerializer):
    class Meta:
        model = GalleryGroup
        fields = ['id', 'image', 'thumbnail']

class GallerySerializer(ModelSerializer):
    same_images = GalleryGroupSerializer(many=True, read_only=True)

    class Meta:
        model = Gallery
        fields = ['id', 'image', 'thumbnail', 'same_images']

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


class ContactFormModelSerializers(ModelSerializer):
    class Meta:
        model = ContactForm
        exclude = 'created',


class ClientEmailModelSerializers(ModelSerializer):
    class Meta:
        model = ClientEmail
        fields = '__all__'


class ProjectPhotoSerializer(ModelSerializer):
    class Meta:
        model = ProjectPhoto
        fields = 'id', 'image', 'thumbnail'


class ProjectListSerializer(ModelSerializer):
    title = CharField(read_only=True)
    location = CharField(read_only=True)
    cover = ImageField(read_only=True)
    cover_thumbnail = ImageField(source='thumbnail', read_only=True)
    photos_count = SerializerMethodField()

    class Meta:
        model = Project
        fields = ('id', 'slug', 'title', 'location', 'year', 'category',
                  'cover', 'cover_thumbnail', 'photos_count')

    def get_photos_count(self, obj):
        return len(obj.photos.all())


class ProjectDetailSerializer(ProjectListSerializer):
    description = CharField(read_only=True)
    materials = CharField(read_only=True)
    photos = ProjectPhotoSerializer(many=True, read_only=True)

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + ('description', 'materials', 'photos')
