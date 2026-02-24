from django.urls import path
from .views import RegistrationView, UserProfileView

urlpatterns = [
    path('register/', RegistrationView.as_view(), name='register'),
    path('me/', UserProfileView.as_view(), name='user_profile'),
]
