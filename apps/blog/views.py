from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from .models import Category, Tag, BlogPost, Comment
from .serializers import (
    CategorySerializer, TagSerializer, BlogPostSerializer,
    BlogPostListSerializer, CommentSerializer
)


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class BlogPostViewSet(viewsets.ModelViewSet):
    queryset = BlogPost.objects.select_related('author', 'category').prefetch_related('tags', 'comments')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content', 'excerpt']
    ordering_fields = ['created_at', 'publish_date', 'view_count']
    ordering = ['-publish_date']
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return BlogPostListSerializer
        return BlogPostSerializer

    @action(detail=True, methods=['post'])
    def increment_views(self, request, pk=None):
        post = self.get_object()
        post.view_count += 1
        post.save()
        return Response({'view_count': post.view_count})

    @action(detail=True, methods=['get'])
    def published(self, request, pk=None):
        posts = BlogPost.objects.filter(is_published=True)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        posts = BlogPost.objects.filter(is_featured=True, is_published=True)[:5]
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    pagination_class = StandardPagination

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        comment = self.get_object()
        comment.is_approved = True
        comment.save()
        return Response({'status': 'comment approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        comment = self.get_object()
        comment.delete()
        return Response({'status': 'comment deleted'})

    @action(detail=False, methods=['get'])
    def by_post(self, request):
        post_id = request.query_params.get('post_id')
        if not post_id:
            return Response({'error': 'post_id required'}, status=status.HTTP_400_BAD_REQUEST)

        comments = Comment.objects.filter(post_id=post_id, is_approved=True)
        serializer = self.get_serializer(comments, many=True)
        return Response(serializer.data)
