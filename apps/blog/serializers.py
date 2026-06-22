from rest_framework import serializers
from .models import Category, Tag, BlogPost, Comment


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'color', 'created_at']
        read_only_fields = ['created_at']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'created_at']
        read_only_fields = ['created_at']


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'author_name', 'author_email', 'content', 'is_approved', 'created_at', 'replies']
        read_only_fields = ['created_at']

    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []


class BlogPostSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'content', 'excerpt', 'featured_image',
            'author_name', 'category', 'category_name', 'tags', 'view_count',
            'read_time', 'is_featured', 'is_published', 'publish_date',
            'comments', 'allow_comments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'view_count']


class BlogPostListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    tag_names = serializers.SlugRelatedField(source='tags', many=True, read_only=True, slug_field='name')

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'excerpt', 'featured_image',
            'author_name', 'category_name', 'tag_names', 'view_count',
            'read_time', 'is_featured', 'is_published', 'publish_date', 'created_at'
        ]
