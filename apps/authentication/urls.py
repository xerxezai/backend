"""
URL configuration for Authentication app
"""

from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/',            views.LoginView.as_view(),           name='login'),
    path('register/',         views.RegisterView.as_view(),         name='register'),
    path('logout/',           views.logout_view,                    name='logout'),
    path('me/',               views.MeView.as_view(),               name='me'),
    path('profile/',          views.ProfileView.as_view(),          name='profile'),
    path('profile/avatar/',   views.AvatarUploadView.as_view(),     name='profile_avatar'),
    path('change-password/',  views.PasswordChangeView.as_view(),   name='change_password'),
    path('forgot-password/',  views.ForgotPasswordView.as_view(),   name='forgot_password'),
    path('verify-otp/',       views.VerifyOTPView.as_view(),        name='verify_otp'),
    path('reset-password/',   views.ResetPasswordView.as_view(),    name='reset_password'),
]
