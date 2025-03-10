from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth import get_user_model
from .models import Store, Transaction
from .serializers import StoreSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime
from django.db.models import Sum

class StoreListView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="모든 가게 목록 조회",
        operation_description="현재 로그인한 사용자의 모든 가게 목록을 반환합니다.",
        responses={200: "가게 목록 반환", 401: "로그인이 필요합니다."}
    )
    def get(self, request):
        """ ✅ 모든 가게 목록 + 현재 월 거래 차트 포함 """
        stores = Store.objects.filter(user=request.user)

        # ✅ 현재 연도 & 월 가져오기
        now = datetime.now()
        current_year, current_month = now.year, now.month

        store_data = []
        for store in stores:
            # ✅ 현재 월의 거래 내역을 `income`, `expense`별로 카테고리 합산
            transactions = Transaction.objects.filter(
                store=store, date__year=current_year, date__month=current_month
            )

            # ✅ 카테고리별 총 수입/지출 계산 (내림차순 정렬 후 최대 3개 제한)
            category_summary = (
                transactions.values("transaction_type", "category__name")
                .annotate(total=Sum("amount"))
                .order_by("-total")[:6]  # ✅ 수입 3개 + 지출 3개 → 최대 6개
            )

            chart_data = [
                {"type": c["transaction_type"], "category": c["category__name"], "cost": float(c["total"])}
                for c in category_summary
            ]

            store_data.append(
                {
                    "store_id": str(store.id),
                    "name": store.name,
                    "address": store.address,
                    "chart": chart_data,  # ✅ 거래 차트 추가
                }
            )

        return Response({"stores": store_data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="새 가게 등록",
        operation_description="새로운 가게를 등록합니다.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='가게 이름'),
                'address': openapi.Schema(type=openapi.TYPE_STRING, description='가게 주소 (선택)'),
            },
            required=['name'],
        ),
        responses={201: "가게 등록 성공", 400: "유효성 검사 실패"}
    )
    def post(self, request):
        serializer = StoreSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StoreDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="특정 가게 조회",
        operation_description="가게 ID를 이용해 해당 가게의 기본 정보를 조회합니다.",
        responses={200: "가게 기본 정보 반환", 404: "가게를 찾을 수 없습니다."}
    )
    def get(self, request, id):
        store = get_object_or_404(Store, id=id, user=request.user)
        return Response({
            "store_id": str(store.id),
            "name": store.name,
            "address": store.address
        })

    @swagger_auto_schema(
        operation_summary="가게 정보 수정",
        operation_description="가게 ID를 이용해 가게 정보를 수정합니다.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='가게 이름'),
                'address': openapi.Schema(type=openapi.TYPE_STRING, description='가게 주소 (선택)'),
            },
            required=['name'],
        ),
        responses={200: "가게 수정 성공", 400: "유효성 검사 실패", 404: "가게를 찾을 수 없습니다."}
    )
    def put(self, request, id):
        store = get_object_or_404(Store, id=id, user=request.user)
        serializer = StoreSerializer(store, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="가게 삭제",
        operation_description="가게 ID를 이용해 해당 가게를 삭제합니다.",
        responses={204: "가게 삭제 성공", 404: "가게를 찾을 수 없습니다."}
    )
    def delete(self, request, id):
        store = get_object_or_404(Store, id=id, user=request.user)
        store.delete()
        return Response({"message": "가게가 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)


