from django.urls import path

from .views import SendRegistrationCodeView


urlpatterns = [
    path(
        'registration-code/',
        SendRegistrationCodeView.as_view(),
        name='send-registration-code',
    ),
]