"""MediaCrawler 研究结果的可选 SQLite 长期数据层。

为保证 ``python -m storage.db`` 和 ``python -m storage.import_run`` 没有
模块预加载副作用，公开 API 从各子模块显式导入。
"""
