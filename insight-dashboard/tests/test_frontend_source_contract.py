from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_category_drawer_keeps_representative_comments_before_drilldown_results() -> None:
    source = (PROJECT_DIR / "src" / "components" / "CategoryDrawer.tsx").read_text(encoding="utf-8")

    assert source.index("<h3>代表评论</h3>") < source.index('className="drilldown-results"')
