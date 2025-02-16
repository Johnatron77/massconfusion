from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from tv import views

urlpatterns = [
    path('signal_alert_hook/', views.signal_alert_hook, name='signal_alert_hook'),
]

urlpatterns = format_suffix_patterns(urlpatterns)