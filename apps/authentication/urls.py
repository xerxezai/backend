"""
URL configuration for Authentication app
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/',            views.LoginView.as_view(),           name='login'),
    # Generic JWT refresh — works for any token issued by RefreshToken.for_user()
    # (ERP's LoginView and LMA's lma_login both use it), since SimpleJWT's
    # TokenRefreshView only validates the refresh token itself, not who issued it.
    path('refresh/',          TokenRefreshView.as_view(),           name='token_refresh'),
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
