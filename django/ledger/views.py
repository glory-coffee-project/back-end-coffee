from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from store.models import Store, Transaction
from ledger.models import Category
from ledger.serializers import TransactionSerializer, CategorySerializer
from datetime import datetime
from django.db.models import Sum
from datetime import date
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi



# ✅ 1️⃣ 거래 내역 목록 조회 & 생성
class LedgerTransactionListCreateView(APIView):  
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="특정 상점의 모든 거래 내역 조회",
        responses={200: TransactionSerializer(many=True)}
    )    

    def get(self, request, store_id):
        """ ✅ 특정 상점의 모든 거래 내역 조회 """
        store = get_object_or_404(Store, id=store_id, user=request.user)
        transactions = Transaction.objects.filter(store=store)
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="거래 내역 생성",
        request_body=TransactionSerializer,
        responses={201: TransactionSerializer()}
    )

    def post(self, request, store_id):
        """ ✅ 거래 내역 생성 """
        data = request.data.copy()
        data["store_id"] = str(store_id)  # 🔹 store_id 추가

        serializer = TransactionSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            transaction = serializer.save()
            return Response(TransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ✅ 2️⃣ 특정 거래 내역 조회, 수정, 삭제
class LedgerTransactionDetailView(APIView):  
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="특정 거래 내역 조회",
        responses={200: TransactionSerializer()}
    )    

    def get(self, request, store_id, transaction_id):
        """ ✅ 특정 거래 내역 조회 """
        store = get_object_or_404(Store, id=store_id, user=request.user)
        transaction = get_object_or_404(Transaction, id=transaction_id, store=store)
        serializer = TransactionSerializer(transaction)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @swagger_auto_schema(
        operation_summary="특정 거래 내역 수정",
        request_body=TransactionSerializer,
        responses={200: TransactionSerializer()}
    )

    def put(self, request, store_id, transaction_id):
        """ ✅ 특정 거래 내역 수정 """
        store = get_object_or_404(Store, id=store_id, user=request.user)
        transaction = get_object_or_404(Transaction, id=transaction_id, store=store)

        # 🔥 요청 데이터 복사 후 category 처리
        data = request.data.copy()
        
        category_input = data.get("category")  # ✅ category 값 확인

        if category_input:
            if category_input.isdigit():  
                # ✅ 숫자이면 기존 Category ID로 조회
                category = get_object_or_404(Category, id=int(category_input))
            else:
                # ✅ 문자열이면 카테고리명으로 조회 or 생성
                category, _ = Category.objects.get_or_create(name=category_input)

            data["category"] = category.id  # ✅ ForeignKey에는 ID 저장

        serializer = TransactionSerializer(transaction, data=data, partial=True, context={"request": request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="특정 거래 내역 삭제",
        responses={204: "삭제 완료"}
    )

    def delete(self, request, store_id, transaction_id):
        """ ✅ 특정 거래 내역 삭제 """
        store = get_object_or_404(Store, id=store_id, user=request.user)
        transaction = get_object_or_404(Transaction, id=transaction_id, store=store)
        transaction.delete()
        return Response({"message": "삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)


# ✅ 3️⃣ 카테고리 목록 조회 & 생성
class CategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="특정 월의 거래 내역 조회",
        manual_parameters=[
            openapi.Parameter("year", openapi.IN_QUERY, description="조회할 연도", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter("month", openapi.IN_QUERY, description="조회할 월", type=openapi.TYPE_INTEGER, required=True)
        ],
        responses={200: "캘린더 및 차트 데이터 반환"}
    )

    def get(self, request):
        """ ✅ 모든 카테고리 목록 조회 """
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="새로운 카테고리 추가",
        request_body=CategorySerializer,
        responses={201: CategorySerializer(), 400: "유효성 검사 실패"}
    )

    def post(self, request):
        """ ✅ 새로운 카테고리 추가 """
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ✅ 4️⃣ 특정 카테고리 조회, 수정, 삭제 (`category_id`를 UUID로 변경)
class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="특정 카테고리 조회",
        responses={200: CategorySerializer()}
    )

    def get(self, request, category_id):
        """ ✅ 특정 카테고리 조회 """
        category = get_object_or_404(Category, id=category_id)
        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="특정 카테고리 수정",
        request_body=CategorySerializer,
        responses={200: CategorySerializer(), 400: "유효성 검사 실패"}
    )

    def put(self, request, category_id):
        """ ✅ 특정 카테고리 수정 """
        category = get_object_or_404(Category, id=category_id)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="특정 카테고리 삭제",
        responses={204: "삭제 완료"}
    )

    def delete(self, request, category_id):
        """ ✅ 특정 카테고리 삭제 """
        category = get_object_or_404(Category, id=category_id)
        category.delete()
        return Response({"message": "삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)
    
    
    # ✅ 5️⃣ 특정 월의 거래 내역을 조회 (캘린더 API)
from django.db.models import Sum

class LedgerCalendarView(APIView):  
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="특정 월 또는 특정 날짜의 거래 내역 조회",
        manual_parameters=[
            openapi.Parameter("year", openapi.IN_QUERY, description="조회할 연도", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter("month", openapi.IN_QUERY, description="조회할 월", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter("day", openapi.IN_QUERY, description="조회할 일", type=openapi.TYPE_INTEGER, required=False),
        ],
        responses={200: "달력 & 차트 데이터 반환"}
    )

    def get(self, request, store_id):
        """ ✅ 특정 월의 거래 내역 조회 (day가 있으면 특정 날짜의 거래 내역 반환) """
        year = request.GET.get("year")
        month = request.GET.get("month")
        day = request.GET.get("day")  # ✅ day 추가

        print(f"📌 [DEBUG] 요청된 파라미터 - year: {year}, month: {month}, day: {day}")  # ✅ 입력값 확인

        if not year or not month:
            return Response({"error": "year와 month 쿼리 파라미터가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            year = int(year)
            month = int(month)
            day = int(day) if day else None  # ✅ day가 있을 경우 int 변환
        except ValueError:
            return Response({"error": "year, month, day는 숫자여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ 상점 확인
        store = get_object_or_404(Store, id=store_id, user=request.user)

        # ✅ 거래 필터링
        filters = {"store": store, "date__year": year, "date__month": month}
        if day:
            filters["date__day"] = day  # ✅ day 필터 추가

        transactions = Transaction.objects.filter(**filters)

        print(f"📌 [DEBUG] SQL Query: {transactions.query}")  # ✅ 실제 SQL 확인
        print(f"📌 [DEBUG] 필터링된 거래 개수: {transactions.count()}")  # ✅ 데이터 개수 확인
        print(f"📌 [DEBUG] 필터링된 거래 목록: {list(transactions.values('date', 'amount', 'transaction_type'))}")  # ✅ 실제 데이터 확인

        if day:
            # ✅ 특정 날짜의 거래 내역 응답
            response_data = [
                {
                    "transaction_id": str(t.id),
                    "type": t.transaction_type,
                    "category": t.category.name if t.category else "미분류",
                    "detail": t.description or "",
                    "cost": float(t.amount)
                }
                for t in transactions
            ]
        else:
            # ✅ 특정 월의 달력 & 차트 데이터 응답
            day_summary = {}
            for t in transactions:
                trans_day = t.date.day
                if trans_day not in day_summary:
                    day_summary[trans_day] = {"hasIncome": False, "hasExpense": False}

                if t.transaction_type == "income":
                    day_summary[trans_day]["hasIncome"] = True
                else:
                    day_summary[trans_day]["hasExpense"] = True

            days_list = [{"day": d, **summary} for d, summary in day_summary.items()]

            category_summary = transactions.values("transaction_type", "category__name").annotate(
                total=Sum("amount")
            ).order_by("-total")[:5]

            category_data = [
                {
                    "type": c["transaction_type"],
                    "category": c["category__name"] if c["category__name"] else "미분류",
                    "total": float(c["total"])
                }
                for c in category_summary
            ]

            response_data = {
                "days": days_list,
                "chart": {
                    "totalIncome": transactions.filter(transaction_type="income").aggregate(Sum("amount"))["amount__sum"] or 0,
                    "totalExpense": transactions.filter(transaction_type="expense").aggregate(Sum("amount"))["amount__sum"] or 0,
                    "categories": category_data,
                }
            }

        return Response(response_data, status=status.HTTP_200_OK)


