"""
Authentication views for XERXEZ Backend
Provides secure authentication endpoints
"""

from django.contrib.auth.models import User
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    PasswordChangeSerializer,
)


class LoginView(generics.GenericAPIView):
    """
    User login endpoint
    """
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(request_body=LoginSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(request_body=RegisterSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)

        return Response(
            {
                "message": "User registered successfully",
                "token": token.key,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(request_body=None)
def logout_view(request):
    """
    User logout endpoint
    """
    try:
        request.user.auth_token.delete()

        return Response(
            {"message": "Successfully logged out"},
            status=status.HTTP_200_OK,
        )

    except Token.DoesNotExist:
        return Response(
            {"message": "User was not logged in"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    User profile endpoint
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordChangeView(generics.GenericAPIView):
    """
    Password change endpoint
    """
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(request_body=PasswordChangeSerializer)
    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        Token.objects.filter(user=request.user).delete()
        new_token = Token.objects.create(user=request.user)

        return Response(
            {
                "message": "Password changed successfully",
                "token": new_token.key,
            },
            status=status.HTTP_200_OK,
        )