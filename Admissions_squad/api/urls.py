from django.urls import path, include
from accounts.views import (
    UserProfileView, UserListView, UserDetailView, ChangePasswordView,
    RoleListCreateView, RoleDetailView
)
from authorizations.views import LoginView, RegistrationView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Аутентификация и регистрация
    path('users/auth/token/', LoginView.as_view(), name='token_obtain_pair'),
    path('users/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/register/', RegistrationView.as_view(), name='register'),
    
    # Профиль текущего пользователя
    path('users/me/', UserProfileView.as_view(), name='user_profile'),
    path('users/me/change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Управление пользователями (только для администраторов)
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    
    # Управление ролями (только для администраторов)
    path('users/roles/', RoleListCreateView.as_view(), name='role_list_create'),
    path('users/roles/<int:pk>/', RoleDetailView.as_view(), name='role_detail'),
]