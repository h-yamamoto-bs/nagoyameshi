from time import perf_counter
from django.db import connection
from django.utils.deprecation import MiddlewareMixin
import os
import json


class QueryLogMiddleware(MiddlewareMixin):
    """
    データベースクエリ数とレスポンス時間を監視するミドルウェア
    環境変数 LOG_DB_QUERIES=1 で有効化
    """
    
    def process_request(self, request):
        request._ql_start = perf_counter()
        # デバッグモードでない場合もクエリを記録できるようにする
        if os.getenv("LOG_DB_QUERIES") == "1":
            connection.force_debug_cursor = True

    def process_response(self, request, response):
        if os.getenv("LOG_DB_QUERIES") == "1":
            duration_ms = None
            try:
                duration_ms = int((perf_counter() - getattr(request, "_ql_start", perf_counter())) * 1000)
            except Exception:
                pass
            
            queries = getattr(connection, "queries", [])
            total_time_ms = int(sum(float(q.get("time", 0)) for q in queries) * 1000)
            
            # 10クエリ以上または500ms以上の場合はWARNレベルでログ出力
            log_level = "WARN" if (len(queries) >= 10 or total_time_ms >= 500) else "INFO"
            
            print(json.dumps({
                "level": log_level,
                "msg": "db_queries",
                "path": request.path,
                "method": request.method,
                "status": getattr(response, "status_code", None),
                "count": len(queries),
                "total_ms": total_time_ms,
                "req_ms": duration_ms,
                "user": str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else "anonymous"
            }))
            
            # 後続に影響しないよう戻す
            connection.force_debug_cursor = False
        
        return response
