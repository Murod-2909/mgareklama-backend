from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import translation
from rest_framework.generics import ListAPIView, RetrieveAPIView, CreateAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle

from apps.notifications import notify_new_contact
from apps.models import Gallery, SiteSetting, Partner, Service, ContactForm, ClientEmail, Project, ProjectPhoto
from apps.serializers import SiteSettingSerializer, PartnerModelSerializer, \
    ServiceModelSerializer, ContactFormModelSerializers, ClientEmailModelSerializers, GallerySerializer, \
    ProjectListSerializer, ProjectDetailSerializer


class GalleryListAPIView(ListAPIView):
    queryset = Gallery.objects.prefetch_related('same_images').order_by('-id')
    serializer_class = GallerySerializer


class SiteSettingView(RetrieveAPIView):
    queryset = SiteSetting.objects.all()
    serializer_class = SiteSettingSerializer

    def get_object(self):
        return SiteSetting.objects.get_or_create(pk=1)[0]


class PartnerListAPIView(ListAPIView):
    queryset = Partner.objects.all()
    serializer_class = PartnerModelSerializer

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

@extend_schema(
    parameters=[
        OpenApiParameter(
            name='lang',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Language code (en, ru, uz)'
        )
    ]
)
class ServiceListAPIView(ListAPIView):
    queryset = Service.objects.order_by('-id')
    serializer_class = ServiceModelSerializer

    def get_queryset(self):
        lang = self.request.GET.get('lang') or 'en'
        translation.activate(lang)
        self.request.LANGUAGE_CODE = lang

        queryset = super().get_queryset()
        return queryset.active_translations(lang).prefetch_related('works')


class ContactDailyThrottle(SimpleRateThrottle):
    scope = 'contact_day'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class ContactFormCreateAPIView(CreateAPIView):
    model = ContactForm
    serializer_class = ContactFormModelSerializers
    throttle_classes = [ScopedRateThrottle, ContactDailyThrottle]
    throttle_scope = 'contact'

    def create(self, request, *args, **kwargs):
        if str(request.data.get('website', '')).strip():  # honeypot: pretend success, store nothing
            fields = ('name', 'email', 'phone', 'subject', 'message')
            return Response({'id': None, **{f: str(request.data.get(f, ''))[:3000] for f in fields}}, status=201)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        lang = serializer.validated_data.get('lang') or 'en'
        contact = serializer.save()
        transaction.on_commit(lambda: notify_new_contact(contact, lang))


class EmailCreateAPIView(CreateAPIView):
    queryset = ClientEmail.objects.all()
    serializer_class = ClientEmailModelSerializers
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'newsletter'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscriber, created = ClientEmail.objects.get_or_create(email=serializer.validated_data['email'])
        return Response({'id': subscriber.pk, 'email': subscriber.email}, status=201 if created else 200)


LANG_PARAMETER = OpenApiParameter(
    name='lang',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description='Language code (en, ru, uz). Projects without a translation in this language are hidden.'
)


class ProjectQuerysetMixin:
    def get_queryset(self):
        lang = self.request.GET.get('lang') or 'en'
        if lang not in dict(settings.LANGUAGES):
            lang = 'en'
        translation.activate(lang)
        self.request.LANGUAGE_CODE = lang

        return (Project.objects.filter(is_published=True)
                .active_translations(lang)
                .annotate(has_video=Exists(ProjectPhoto.objects.filter(project=OuterRef('pk'), media_type='video')))
                .prefetch_related('photos', 'translations'))


@extend_schema(parameters=[LANG_PARAMETER])
class ProjectListAPIView(ProjectQuerysetMixin, ListAPIView):
    serializer_class = ProjectListSerializer


@extend_schema(parameters=[LANG_PARAMETER])
class ProjectDetailAPIView(ProjectQuerysetMixin, RetrieveAPIView):
    serializer_class = ProjectDetailSerializer
    lookup_field = 'slug'

    def get_object(self):
        self.kwargs['slug'] = self.kwargs['slug'].lower()
        return super().get_object()
