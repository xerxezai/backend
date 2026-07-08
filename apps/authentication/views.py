"""
Authentication views for XERXEZ Backend — JWT-based
"""
import secrets

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

User = get_user_model()
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_yasg.utils import swagger_auto_schema

from .models import OTPToken
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    AvatarUploadSerializer,
    PasswordChangeSerializer,
    ForgotPasswordSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
)
from rest_framework.parsers import MultiPartParser, FormParser


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


class AvatarUploadView(generics.UpdateAPIView):
    """PATCH /api/v1/auth/profile/avatar/ — multipart avatar upload."""
    serializer_class = AvatarUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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
        refresh = RefreshToken.for_user(request.user)
        return Response({
            'message': 'Password changed successfully',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(generics.GenericAPIView):
    """POST /api/v1/auth/forgot-password/ — generates and emails a 6-digit OTP."""
    serializer_class = ForgotPasswordSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        if User.objects.filter(email=email, is_active=True).exists():
            otp_obj = OTPToken.generate_for_email(email)
            try:
                send_mail(
                    subject='XERXEZ ERP – Password Reset OTP',
                    message=(
                        f'Your one-time password (OTP) for XERXEZ ERP is:\n\n'
                        f'  {otp_obj.otp}\n\n'
                        f'This code expires in 10 minutes.\n'
                        f'If you did not request a password reset, please ignore this email.'
                    ),
                    from_email=None,
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass

        # Always return the same message — don't leak whether the email exists.
        return Response(
            {'message': 'If that email is registered you will receive an OTP shortly.'},
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(generics.GenericAPIView):
    """POST /api/v1/auth/verify-otp/ — validates OTP, returns a short-lived reset token."""
    serializer_class = VerifyOTPSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp   = serializer.validated_data['otp']

        otp_obj = (
            OTPToken.objects
            .filter(email=email, otp=otp, is_used=False)
            .order_by('-created_at')
            .first()
        )

        if not otp_obj or timezone.now() > otp_obj.expires_at:
            return Response(
                {'error': 'Invalid or expired OTP.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from datetime import timedelta
        reset_token = secrets.token_urlsafe(32)
        otp_obj.reset_token = reset_token
        otp_obj.is_used     = True
        otp_obj.expires_at  = timezone.now() + timedelta(minutes=15)
        otp_obj.save(update_fields=['reset_token', 'is_used', 'expires_at'])

        return Response({'reset_token': reset_token, 'message': 'OTP verified'})


class ResetPasswordView(generics.GenericAPIView):
    """POST /api/v1/auth/reset-password/ — sets the new password using the reset token."""
    serializer_class = ResetPasswordSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_token  = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']

        otp_obj = (
            OTPToken.objects
            .filter(reset_token=reset_token, is_used=True)
            .order_by('-created_at')
            .first()
        )

        if not otp_obj or timezone.now() > otp_obj.expires_at:
            return Response(
                {'error': 'Reset token is invalid or has expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=otp_obj.email, is_active=True)
        except User.DoesNotExist:
            return Response(
                {'error': 'User account not found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()
        otp_obj.delete()

        return Response({'message': 'Password reset successfully.'})
