from django.urls import path

from .views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationRetryEmailView,
    NotificationUnreadCountView,
    SendRegistrationCodeView,
)


urlpatterns = [
    path(
        "registration-code/",
        SendRegistrationCodeView.as_view(),
        name="send_registration_code",
    ),
    path(
        "",
        NotificationListView.as_view(),
        name="notifications_list",
    ),
    path(
        "unread-count/",
        NotificationUnreadCountView.as_view(),
        name="notifications_unread_count",
    ),
    path(
        "<int:pk>/read/",
        NotificationMarkReadView.as_view(),
        name="notifications_mark_read",
    ),
    path(
        "<int:pk>/retry-email/",
        NotificationRetryEmailView.as_view(),
        name="notifications_retry_email",
    ),
    path(
        "read-all/",
        NotificationMarkAllReadView.as_view(),
        name="notifications_mark_all_read",
    ),
]