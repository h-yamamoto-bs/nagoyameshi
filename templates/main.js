document.addEventListener('DOMContentLoaded', function() {

    // DOM要素の取得
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const searchForm = document.getElementById('search-form');

    // 要素の存在確認
    if (searchInput && searchButton && searchForm) {

        // 検索ボタンのクリックイベント
        searchButton.addEventListener('click', function(event) {
            event.preventDefault(); // フォームのデフォルト送信を防ぐ
            performSearch();
        });

        // Enterキーでフォーム送信
        searchInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault(); // Enterキーのデフォルト動作を防ぐ
                performSearch();
            }
        });
    }

});

// 検索処理関数
function performSearch() {

    // 要素の再取得
    const searchInput = document.getElementById('search-input');

    // 入力値の取得
    const query = searchInput.value.trim();

    // 入力値検証
    if (query) {
        window.location.href = `/shops/search/?q=${encodeURIComponent(query)}`;
    } else {
        alert('検索キーワードを入力してください。');
    }

}