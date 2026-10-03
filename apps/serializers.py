from rest_framework.serializers import ModelSerializer, CharField

from apps.models import Gallery, SiteSetting, Partner, Service, ServiceWork, ContactForm, ClientEmail, GalleryGroup


class GalleryGroupSerializer(ModelSerializer):
    class Meta:
        model = GalleryGroup
        fields = ['id', 'image']

class GallerySerializer(ModelSerializer):
    same_images = GalleryGroupSerializer(many=True, read_only=True)

    class Meta:
        model = Gallery
        fields = ['id', 'image', 'same_images']

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
        fields = 'id', 'image'


class ServiceModelSerializer(ModelSerializer):
    title = CharField(read_only=True)
    description = CharField(read_only=True)
    works = ServiceWorkSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = 'id', 'title', 'description', 'image', 'works'


class ContactFormModelSerializers(ModelSerializer):
    class Meta:
        model = ContactForm
        exclude = 'created',


class ClientEmailModelSerializers(ModelSerializer):
    class Meta:
        model = ClientEmail
        fields = '__all__'
