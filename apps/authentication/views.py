"""
Authentication views for SEOZ Backend
Provides secure authentication endpoints
"""

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    LoginSerializer, 
    RegisterSerializer, 
    UserSerializer, 
    PasswordChangeSerializer
)


class LoginView(generics.GenericAPIView):
    """
    User login endpoint
    """
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        responses={
            200: openapi.Response(
                description="Login successful",
                examples={
                    "application/json": {
                        "token": "your-auth-token",
                        "user": {
                            "id": 1,
                            "username": "user",
                            "email": "user@example.com"
                        }
                    }
                }
            )
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create token for new user
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'User registered successfully',
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """
    User logout endpoint
    """
    try:
        # Delete the user's token
        request.user.auth_token.delete()
        return Response({'message': 'Successfully logged out'}, 
                       status=status.HTTP_200_OK)
    except Token.DoesNotExist:
        return Response({'message': 'User was not logged in'}, 
                       status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    User profile view and update
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
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Delete old token and create new one for security
        Token.objects.filter(user=request.user).delete()
        new_token = Token.objects.create(user=request.user)
        
        return Response({
            'message': 'Password changed successfully',
            'token': new_token.key
        })