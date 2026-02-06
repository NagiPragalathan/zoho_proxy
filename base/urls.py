from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('zoho/login/', views.zoho_login, name='zoho_login'),
    path('api/oauth/zoho/callback/', views.zoho_callback, name='zoho_callback'),
    path('api/leads/', views.proxy_lead, name='proxy_lead'),
    path('account/primary/<int:pk>/', views.set_primary, name='set_primary'),
    path('account/delete/<int:pk>/', views.delete_account, name='delete_account'),
]
