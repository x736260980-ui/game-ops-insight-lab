from .app_factory import create_app


app = create_app("bilibili", chrome_port=9223)

