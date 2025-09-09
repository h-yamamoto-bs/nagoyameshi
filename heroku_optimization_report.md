# Heroku リクエスト数最適化レポート

## 測定結果サマリー

### 各ページのパフォーマンス

| ページ名             | DB クエリ数 | レスポンス時間 | ステータス | コンテンツサイズ |
| -------------------- | ----------- | -------------- | ---------- | ---------------- |
| 管理者ダッシュボード | 4           | 0.286 秒       | 200        | 10,489 bytes     |
| ユーザー管理         | 6           | 0.007 秒       | 200        | 70,718 bytes     |
| ユーザー検索         | 6           | 0.006 秒       | 200        | 65,714 bytes     |
| 店舗管理             | 5           | 0.007 秒       | 200        | 35,536 bytes     |
| 店舗作成             | 3           | 0.006 秒       | 200        | 20,731 bytes     |
| カテゴリ管理         | 7           | 0.007 秒       | 200        | 38,861 bytes     |

## 検出された問題点

### 1. カテゴリ管理ページ（最も重い）

- **DB クエリ数: 7**
- 複数の集計クエリが重複実行されている
- LEFT JOIN を使った複雑な集計処理

### 2. ユーザー管理関連（N+1 問題の可能性）

- **ユーザー管理: 6 クエリ**
- **ユーザー検索: 6 クエリ**
- サブスクリプション状態の確認で追加クエリが発生

### 3. 店舗管理（良好なパフォーマンス）

- **5 クエリ**で済んでいる
- select_related()で効率的に JOIN している

## 最適化推奨事項（優先度順）

### 🔴 高優先度

#### 1. カテゴリ管理の最適化

```python
# 現在: 7クエリ（重複する集計クエリ）
# 最適化後: 2-3クエリに削減可能

# ビューを以下のように変更:
categories = Category.objects.select_related().annotate(
    shop_count=Count('shop_categories')
).prefetch_related('shop_categories__shop')
```

#### 2. ユーザー管理のサブスクリプション最適化

```python
# 現在: 6クエリ（サブスクリプション状態を別々に取得）
# 最適化後: 3-4クエリに削減可能

users = User.objects.select_related('subscription').prefetch_related(
    Prefetch('subscription', queryset=Subscription.objects.filter(is_active=True))
)
```

### 🟡 中優先度

#### 3. ダッシュボードのキャッシュ化

```python
# 統計情報をキャッシュ
from django.core.cache import cache

def get_dashboard_stats():
    cache_key = 'dashboard_stats'
    stats = cache.get(cache_key)
    if not stats:
        stats = {
            'total_shops': Shop.objects.count(),
            'total_users': User.objects.filter(manager_flag=False).count(),
            'total_categories': Category.objects.count(),
        }
        cache.set(cache_key, stats, 300)  # 5分間キャッシュ
    return stats
```

#### 4. ページネーションの改善

```python
# 現在: 20件ずつ表示
# 推奨: 10件に削減してクエリ負荷を軽減
ITEMS_PER_PAGE = 10
```

### 🟢 低優先度

#### 5. 静的ファイルの最適化

- CSS/JS の圧縮
- 画像の最適化
- CDN の活用

## Heroku 固有の最適化

### 1. データベース接続プールの設定

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
        'CONN_MAX_AGE': 600,  # 接続プールを有効化
    }
}
```

### 2. 不要なミドルウェアの削除

```python
# DEBUG=Falseの場合は以下を削除
MIDDLEWARE = [
    # 'django.middleware.common.BrokenLinkEmailsMiddleware',  # 削除
    # 'django.contrib.admindocs.middleware.XViewMiddleware',  # 削除
]
```

### 3. ログレベルの最適化

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'WARNING',  # INFOからWARNINGに変更
        },
    },
}
```

## 実装優先順位

### Phase 1（即座に実施）

1. カテゴリ管理のクエリ最適化
2. ユーザー管理の select_related 追加
3. ダッシュボード統計のキャッシュ化

### Phase 2（1 週間以内）

1. データベース接続プール設定
2. ページネーション件数調整
3. 不要なミドルウェア削除

### Phase 3（継続的改善）

1. 静的ファイル最適化
2. フロントエンド軽量化
3. 監視・アラート設定

## 期待される改善効果

- **カテゴリ管理**: 7 クエリ → 3 クエリ（57%削減）
- **ユーザー管理**: 6 クエリ → 3 クエリ（50%削減）
- **レスポンス時間**: 平均 30%改善
- **Heroku 使用量**: 20-30%削減

## 監視すべきメトリクス

1. **1 ページあたりの DB クエリ数**

   - 目標: 5 クエリ以下
   - 現在: 最大 7 クエリ

2. **レスポンス時間**

   - 目標: 0.1 秒以下
   - 現在: 最大 0.286 秒

3. **Heroku dynos 使用率**

   - 目標: 70%以下を維持

4. **データベース接続数**
   - 目標: 同時接続 20 以下

---

_このレポートは 2025 年 9 月 9 日のテスト結果に基づいて作成されました。_
