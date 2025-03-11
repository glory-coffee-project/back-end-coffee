from rest_framework import serializers
from .models import Recipe, RecipeItem
from inventory.models import Inventory
from ingredients.models import Ingredient  
from django.shortcuts import get_object_or_404
from decimal import Decimal
from .utils import calculate_recipe_cost
import logging
from django.db import transaction
from rest_framework import serializers
from .recipe_item_serializers import RecipeItemSerializer



logger = logging.getLogger(__name__)

# ✅ 레시피(Recipe) 시리얼라이저
class RecipeSerializer(serializers.ModelSerializer):
    recipe_name = serializers.CharField(source="name")
    recipe_cost = serializers.DecimalField(source="sales_price_per_item", max_digits=10, decimal_places=2, required=False)  # ✅ 선택 값
    recipe_img = serializers.ImageField(required=False)
    ingredients = RecipeItemSerializer(many=True, write_only=True, required=False)  # ✅ 선택 값
    production_quantity = serializers.IntegerField(source="production_quantity_per_batch", required=False)  # ✅ 선택 값
    total_ingredient_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    production_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Recipe
        fields = [
                'id', 'recipe_name', 'recipe_cost', 'recipe_img', 
                'is_favorites', 'ingredients', 'production_quantity', 
                'total_ingredient_cost', 'production_cost'
        ]
        read_only_fields = ['id']
        
    def get_ingredients(self, obj):
        from .serializers import RecipeItemSerializer  # 🔥 여기서 지연 임포트
        recipe_items = RecipeItem.objects.filter(recipe=obj)
        return RecipeItemSerializer(recipe_items, many=True).data    

    def validate(self, data):
        """🚀 빈 값이면 DB에서 기존 값 가져오기"""
        instance = self.instance  # ✅ 기존 Recipe 객체 (PUT 요청 시)

        if instance:
            data.setdefault("sales_price_per_item", instance.sales_price_per_item)  # ✅ 기존 값 유지
            data.setdefault("production_quantity_per_batch", instance.production_quantity_per_batch)  # ✅ 기존 값 유지

        return data

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients', [])  
        recipe = Recipe.objects.create(**validated_data)

        ingredient_costs = []  # ✅ 원가 계산 리스트

        for ingredient_data in ingredients_data:
            ingredient = get_object_or_404(Ingredient, id=ingredient_data["ingredient_id"])
            required_amount = Decimal(str(ingredient_data["quantity_used"]))
            
            print(f"🔍 Ingredient: {ingredient.name}, Unit Cost: {ingredient.unit_cost}, Required Amount: {required_amount}")  # ✅ 디버깅

            inventory, created = Inventory.objects.get_or_create(
                ingredient=ingredient,
                defaults={"remaining_stock": ingredient.purchase_quantity}
            )

            if inventory.remaining_stock < required_amount:
                raise serializers.ValidationError(
                    f"{ingredient.name} 재고가 부족합니다. (남은 재고: {inventory.remaining_stock})"
                )

            inventory.remaining_stock = Decimal(str(inventory.remaining_stock))  # ✅ Decimal로 변환
            inventory.remaining_stock -= required_amount  # ✅ 같은 타입끼리 연산
            inventory.save()

            unit = ingredient_data.get("unit", None)

            RecipeItem.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                quantity_used=required_amount,
                unit=unit
            )

            ingredient_costs.append({
                "ingredient_id": str(ingredient.id),
                "ingredient_name": ingredient.name,
                "unit_price": ingredient.unit_cost,  
                "quantity_used": required_amount,
                "unit": unit
            })

        print(f"📝 Ingredient Costs List: {ingredient_costs}")  # ✅ ingredient_costs 리스트 확인

        # ✅ 원가 계산 후 DB에 저장
        cost_data = calculate_recipe_cost(
            ingredients=ingredient_costs,
            sales_price_per_item=recipe.sales_price_per_item,  
            production_quantity_per_batch=recipe.production_quantity_per_batch  
        )

        print(f"Before Save: {cost_data['total_material_cost']}, {cost_data['cost_per_item']}")  # ✅ 값 확인

        recipe.total_ingredient_cost = Decimal(str(cost_data["total_material_cost"]))
        recipe.production_cost = Decimal(str(cost_data["cost_per_item"]))

        with transaction.atomic():
            Recipe.objects.filter(id=recipe.id).update(
                total_ingredient_cost=recipe.total_ingredient_cost,
                production_cost=recipe.production_cost
            )

        updated_recipe = Recipe.objects.get(id=recipe.id)
        print(f"[DB Stored] total_ingredient_cost: {updated_recipe.total_ingredient_cost}, production_cost: {updated_recipe.production_cost}")

        return updated_recipe  # ✅ 시리얼라이저에 반영

    def get_total_ingredient_cost(self, obj):
        """✅ 응답에 `total_ingredient_cost` 추가 (None 방지)"""
        return getattr(obj, "total_ingredient_cost", 0)

    def get_production_cost(self, obj):
        """✅ 응답에 `production_cost` 추가 (None 방지)"""
        return getattr(obj, "production_cost", 0)

    def to_representation(self, instance):
        """🚀 응답 데이터에서 `recipe_cost`가 `None`이면 기본값을 `0`으로 설정"""
        data = super().to_representation(instance)
        data["recipe_cost"] = data["recipe_cost"] if data["recipe_cost"] is not None else 0  # ✅ None → 0 변환
        return data
