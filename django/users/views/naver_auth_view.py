import os
import requests
import logging
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from users.utils import store_refresh_token  
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from datetime import datetime


# 로깅 설정
logger = logging.getLogger(__name__)

User = get_user_model()

@method_decorator(csrf_exempt, name='dispatch')
class NaverExchangeCodeForToken(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        logger.info("🔍 Naver OAuth 요청 시작")
        
        code = request.data.get("code")
        state = request.data.get("state")
        logger.info(f"📌 받은 Authorization Code: {code}, State: {state}")

        if not code or not state:
            logger.error("❌ Authorization Code 또는 State 값이 없습니다.")
            return JsonResponse({"error": "Authorization code or state is missing"}, status=400)

        token_endpoint = "https://nid.naver.com/oauth2.0/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": os.getenv("NAVER_CLIENT_ID"),
            "client_secret": os.getenv("NAVER_CLIENT_SECRET"),
            "code": code,
            "state": state,
        }

        try:
            # ✅ Naver에서 액세스 토큰 요청
            response = requests.post(token_endpoint, data=data)
            logger.info(f"📌 Naver OAuth 응답 상태 코드: {response.status_code}")

            response.raise_for_status()
            token_data = response.json()
            logger.info(f"📌 Naver OAuth Token Response: {token_data}")

            access_token = token_data.get("access_token")
            if not access_token:
                logger.error("❌ Naver에서 Access Token을 가져오지 못했습니다.")
                return JsonResponse({"error": "Failed to obtain access token"}, status=400)

            # ✅ Naver에서 유저 정보 가져오기
            userinfo_endpoint = "https://openapi.naver.com/v1/nid/me"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_info_response = requests.get(userinfo_endpoint, headers=headers)
            user_info_response.raise_for_status()
            user_info = user_info_response.json().get("response", {})
            logger.info(f"📌 Naver User Info Response: {user_info}")

            email = user_info.get("email")
            full_name = user_info.get("name", "").strip()

            if not email:
                logger.error("❌ Naver User Info에 이메일 정보가 없습니다.")
                return JsonResponse({"error": "Email not found in user info"}, status=400)

            # ✅ 이메일 기준으로 사용자 생성 또는 가져오기
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"first_name": full_name}
            )
            logger.info(f"✅ User 정보: {user} (Created: {created})")

            # ✅ JWT 토큰 생성
            refresh = RefreshToken.for_user(user)
            access_token_obj = refresh.access_token
            access_token = str(access_token_obj)
            refresh_token = str(refresh)
            print("✅ JWT 토큰 생성 완료")

            # ✅ Redis에 Refresh Token 저장
            expires_in = int(access_token_obj['exp'])
            expires_at = datetime.fromtimestamp(expires_in)
            store_refresh_token(user.id, refresh_token, expires_in)
            print(f"✅ Redis에 Refresh Token 저장 완료 (Expires in: {expires_in}s)")
            
            # ✅ AccessToken 블랙리스트에 등록하기 위한 OutstandingToken 저장
            OutstandingToken.objects.get_or_create(
                jti=access_token_obj['jti'],
                defaults={
                    'user': user,
                    'token': access_token,
                    'expires_at': expires_at,
                }
            )

            

            # ✅ 응답 데이터 구성 (Bearer 방식)
            response_data = {
                "access": access_token,
                "refresh": refresh_token
            }
            return JsonResponse(response_data)


        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Naver OAuth 요청 실패: {str(e)}")
            return JsonResponse({"error": f"Naver OAuth Request Failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"❌ 내부 서버 오류 발생: {str(e)}")
            return JsonResponse({"error": f"Internal Server Error: {str(e)}"}, status=500)
