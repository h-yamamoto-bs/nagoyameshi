from django import template

register = template.Library()

@register.filter
def heroku_media_url(url):
    """
    Heroku用にメディアURLを静的ファイルURLに変換する
    """
    if url and url.startswith('/media/'):
        return url.replace('/media/', '/static/')
    return url
