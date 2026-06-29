"""
Authentication views for XERXEZ Backend — JWT-based
"""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_yasg.utils import swagger_auto_schema

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    PasswordChangeSerializer,
)


def _user_payload(user):
    """Build the standard login/me response dict."""
    try:
        role = user.profile.role
    except Exception:
        role = 'admin'
    return {
        'id': user.id,
        'username': user.username,
        'name': user.first_name or user.username,
        'role': role,
        'email': user.email,
    }


class LoginView(generics.GenericAPIView):
    """POST /api/v1/auth/login/ — returns JWT access + refresh tokens."""
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'anon'

    @swagger_auto_schema(request_body=LoginSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        # Update last_login_at on the profile
        try:
            user.profile.last_login_at = timezone.now()
            user.profile.save(update_fields=['last_login_at'])
        except Exception:
            pass

        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            **_user_payload(user),
        }, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register/"""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(request_body=RegisterSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'User registered successfully',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            **_user_payload(user),
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """POST /api/v1/auth/logout/ — blacklists the refresh token."""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            RefreshToken(refresh_token).blacklist()
    except TokenError:
        pass
    return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)


class MeView(generics.RetrieveAPIView):
    """GET /api/v1/auth/me/ — returns current user info."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/auth/profile/"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordChangeView(generics.GenericAPIView):
    """POST /api/v1/auth/change-password/"""
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(request_body=PasswordChangeSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Issue new tokens after password change
        refresh = RefreshToken.for_user(request.user)
        return Response({
            'message': 'Password changed successfully',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)
