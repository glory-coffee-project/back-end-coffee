from django.utils.timezone import now
from django.db.models import Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Store, Transaction
from .serializers import StoreSerializer

class StoreListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="모든 가게 목록 조회",
        operation_description="현재 로그인한 사용자의 모든 가게 목록을 반환합니다.",
        responses={200: "가게 목록 반환", 401: "로그인이 필요합니다."}
    )
    def get(self, request):
        stores = Store.objects.filter(user=request.user)
        store_list = []

        for store in stores:
            transactions = Transaction.objects.filter(
                user=request.user, store=store,
                date__year=now().year, date__month=now().month
            ).values('transaction_type', 'category__name').annotate(total=Sum('amount'))

            chart = [
                {"type": t["transaction_type"], "category": t["category__name"], "cost": t["total"]}
                for t in transactions
            ]

            store_data = {
                "store_id": str(store.id),
                "name": store.name,
                "address": store.address,
                "chart": chart
            }
            store_list.append(store_data)

        return Response(store_list)

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
        try:
            store = Store.objects.get(id=id, user=request.user)
        except Store.DoesNotExist:
            return Response({"detail": "해당 가게를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        store_data = {
            "store_id": str(store.id),
            "name": store.name,
            "address": store.address
        }
        return Response(store_data)

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
        try:
            store = Store.objects.get(id=id, user=request.user)
        except Store.DoesNotExist:
            return Response({"detail": "해당 가게를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

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
        try:
            store = Store.objects.get(id=id, user=request.user)
        except Store.DoesNotExist:
            return Response({"detail": "해당 가게를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        store.delete()
        return Response({"message": "가게가 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)


class StoreCalendarView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="특정 가게 월별 거래 내역 조회",
        operation_description="가게 ID와 year, month를 입력하여 해당 월의 일자별 거래 내역을 조회합니다.",
        manual_parameters=[
            openapi.Parameter('year', openapi.IN_QUERY, description="조회할 연도 (예: 2025)", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('month', openapi.IN_QUERY, description="조회할 월 (예: 1)", type=openapi.TYPE_INTEGER, required=True),
        ],
        responses={200: "월별 거래 내역 반환", 404: "가게를 찾을 수 없습니다."}
    )
    def get(self, request, id):
        year = request.GET.get('year')
        month = request.GET.get('month')

        # year, month 유효성 검사
        if not year or not month:
            return Response({"detail": "year와 month 값을 입력하세요."}, status=status.HTTP_400_BAD_REQUEST)
        if not year.isdigit() or not month.isdigit():
            return Response({"detail": "year와 month는 숫자여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        year, month = int(year), int(month)

        try:
            store = Store.objects.get(id=id, user=request.user)
        except Store.DoesNotExist:
            return Response({"detail": "해당 가게를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        transactions = Transaction.objects.filter(
            user=request.user, store=store,
            date__year=year, date__month=month
        ).values('id', 'date', 'transaction_type', 'category__name', 'description', 'amount')

        date_info = {}
        for t in transactions:
            day = t['date'].day
            entry = {
                "transaction_id": str(t['id']),
                "type": t['transaction_type'],
                "category": t['category__name'],
                "detail": t['description'],
                "cost": t['amount']
            }
            date_info.setdefault(day, []).append(entry)

        return Response({"date_info": sorted([{"day": d, "day_info": info} for d, info in date_info.items()], key=lambda x: x["day"])})
