"""
リクエスト数削減用ミドルウェア
"""
from django.core.cache import cache
from django.http import HttpResponse
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
            
        # 重複リクエストの防止（認証後のユーザーのみ）
        # hasattrでrequest.userの存在確認をしてからアクセス
        if hasattr(request, 'user') and request.user.is_authenticated:
            cache_key = f"user_request_{request.user.id}_{request.path}"
            last_request_time = cache.get(cache_key)
            
            current_time = time.time()
            if last_request_time and (current_time - last_request_time) < 1:  # 1秒以内の重複防止
                return HttpResponse("Too many requests", status=429)
                
            cache.set(cache_key, current_time, 5)  # 5秒間記録
        
        response = self.get_response(request)
        return response
