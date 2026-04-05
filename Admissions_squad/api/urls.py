from django.urls import path
from accounts.views import UserProfileView, UserListView, UserDetailView, ChangePasswordView, RoleListCreateView, RoleDetailView, UserStudyInfoView, PassportView
from authorizations.views import LoginView, RegistrationView
from rest_framework_simplejwt.views import TokenRefreshView
from squads.views import (
    SquadListCreateView, SquadDetailView,
    SquadMembershipListCreateView, SquadMembershipDetailView,
    MembershipFeeListCreateView, MembershipFeeDetailView
)

urlpatterns = [
    # Пользователи и аутентификация
    path('users/auth/token/', LoginView.as_view(), name='token_obtain_pair'),
    path('users/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/register/', RegistrationView.as_view(), name='register'),
    path('users/me/', UserProfileView.as_view(), name='user_profile'),
    path('users/me/study-info/', UserStudyInfoView.as_view(), name='user_study_info'),
    path('users/me/passport/', PassportView.as_view(), name='user_passport'),
    path('users/me/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('users/roles/', RoleListCreateView.as_view(), name='role_list_create'),
    path('users/roles/<int:pk>/', RoleDetailView.as_view(), name='role_detail'),
    
    # Отряды
    path('squads/', SquadListCreateView.as_view(), name='squad_list_create'),
    path('squads/<int:pk>/', SquadDetailView.as_view(), name='squad_detail'),
    
    # Членство в отрядах
    path('squads/<int:squad_id>/members/', SquadMembershipListCreateView.as_view(), name='squad_members_list_create'),
    path('squads/members/<int:pk>/', SquadMembershipDetailView.as_view(), name='squad_membership_detail'),
    
    # Взносы
    path('squads/members/<int:membership_id>/fees/', MembershipFeeListCreateView.as_view(), name='membership_fees_list_create'),
    path('squads/fees/<int:pk>/', MembershipFeeDetailView.as_view(), name='membership_fee_detail'),
]