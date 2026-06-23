from rest_framework import serializers
from .models import Account, JournalEntry, JournalLine


class AccountSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    class Meta:
        model = Account
        fields = '__all__'


class JournalLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)

    class Meta:
        model = JournalLine
        fields = '__all__'


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)
    is_balanced = serializers.BooleanField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = '__all__'
