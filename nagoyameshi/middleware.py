"""
リクエスト数削減用ミドルウェア
"""
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings
import time

class RequestOptimizationMiddleware:
    """
    リクエスト最適化ミドルウェア
    - 重複リクエストの防止
    - 静的ファイルのキャッシュ制御
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # 静的ファイルへのリクエストにキャッシュヘッダーを追加
        if request.path.startswith('/static/'):
            response = self.get_response(request)
            response['Cache-Control'] = 'public, max-age=86400'  # 24時間キャッシュ
            return response
            
        # 開発環境では重複チェックを無効にする
        if settings.DEBUG:
            response = self.get_response(request)
            return response
            
        # 重複リクエストの防止（認証後のユーザーのみ、本番環境のみ）
        # hasattrでrequest.userの存在確認をしてからアクセス
        if hasattr(request, 'user') and request.user.is_authenticated:
            # POST/PUT/DELETEリクエストのみ重複チェック（GET/HEAD/OPTIONSは除外）
            if request.method in ['POST', 'PUT', 'DELETE']:
                cache_key = f"user_request_{request.user.id}_{request.path}_{request.method}"
                last_request_time = cache.get(cache_key)
                
                current_time = time.time()
                if last_request_time and (current_time - last_request_time) < 0.5:  # 0.5秒以内の重複防止
                    return HttpResponse("Too many requests", status=429)
                    
                cache.set(cache_key, current_time, 2)  # 2秒間記録
        
        response = self.get_response(request)
        return response
