from rest_framework import serializers
from .models import Transaction, Category

# Transaction 시리얼라이저
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'category', 'transaction_type', 'amount', 'description', 'date', 'created_at'] 
        read_only_fields = ['user'] 
# Category 시리얼라이저
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']
