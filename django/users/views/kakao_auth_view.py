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

# 로깅 설정
logger = logging.getLogger(__name__)

User = get_user_model()

@method_decorator(csrf_exempt, name='dispatch')
class KakaoExchangeCodeForToken(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info("🔍 Kakao OAuth 요청 시작")

        code = request.data.get("code")
        logger.info(f"📌 받은 Authorization Code: {code}")

        if not code:
            logger.error("❌ Authorization Code가 없습니다.")
            return JsonResponse({"error": "Authorization code is missing"}, status=400)

        token_endpoint = "https://kauth.kakao.com/oauth/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": os.getenv("KAKAO_CLIENT_ID"),
            "client_secret": os.getenv("KAKAO_CLIENT_SECRET"),  
            "redirect_uri": os.getenv("KAKAO_REDIRECT_URI"),
            "code": code,
        }

        try:
            # ✅ 카카오에서 액세스 토큰 요청
            response = requests.post(token_endpoint, data=data)
            logger.info(f"📌 Kakao OAuth 응답 상태 코드: {response.status_code}")

            response.raise_for_status()
            token_data = response.json()
            logger.info(f"📌 Kakao OAuth Token Response: {token_data}")

            access_token = token_data.get("access_token")
            if not access_token:
                logger.error("❌ Kakao에서 Access Token을 가져오지 못했습니다.")
                return JsonResponse({"error": "Failed to obtain access token"}, status=400)

            # ✅ 카카오에서 사용자 정보 가져오기
            userinfo_endpoint = "https://kapi.kakao.com/v2/user/me"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_info_response = requests.get(userinfo_endpoint, headers=headers)
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            logger.info(f"📌 Kakao User Info Response: {user_info}")

            kakao_account = user_info.get("kakao_account", {})

            # ✅ 디버깅 추가: kakao_account가 존재하는지 확인
            if not kakao_account:
                logger.error("❌ Kakao 응답에서 kakao_account를 찾을 수 없습니다.")
                return JsonResponse({"error": "Invalid Kakao response, kakao_account missing"}, status=400)

            email = kakao_account.get("email")
            email_needs_agreement = kakao_account.get("email_needs_agreement", False)

            # ✅ 디버깅 추가: 이메일 정보가 있는지 확인
            logger.info(f"📌 Kakao Account Email: {email}, Needs Agreement: {email_needs_agreement}")

            # ✅ 이메일 제공 동의 여부 체크
            if email_needs_agreement:
                logger.warning("⚠️ 사용자가 이메일 제공에 동의하지 않았습니다.")
                return JsonResponse({"error": "User did not agree to share email"}, status=400)

            if not email:
                logger.error("❌ Kakao User Info에 이메일 정보가 없습니다.")
                return JsonResponse({"error": "Email not found in user info"}, status=400)

            # ✅ `email`을 기준으로 사용자 찾기
            user, created = User.objects.get_or_create(
                email=email
            )
            logger.info(f"✅ User 정보: {user} (Created: {created})")

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            logger.info("✅ JWT 토큰 생성 완료")

            expires_in = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())  
            store_refresh_token(user.id, refresh_token, expires_in)
            logger.info(f"✅ Redis에 Refresh Token 저장 완료 (Expires in: {expires_in}s)")

            response_data = {"access": access_token}
            response = JsonResponse(response_data)

            response.set_cookie(
                "access_token",
                access_token,
                domain=".livflow.co.kr",
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
                samesite="Strict",
            )
            logger.info("✅ 액세스 토큰을 쿠키에 저장 완료")

            return response

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Kakao OAuth 요청 실패: {str(e)}")
            return JsonResponse({"error": f"Kakao OAuth Request Failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"❌ 내부 서버 오류 발생: {str(e)}")
            return JsonResponse({"error": f"Internal Server Error: {str(e)}"}, status=500)
