from pathlib import Path

from painfinder.cross_run import filter_cross_run_duplicates
from painfinder.domain import SourceItem, SourceType
from painfinder.storage import SQLiteResearchRepository


def _item(external_id: str, body: str) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.POST,
        title="Operational problem",
        body=body,
        subreddit="smallbusiness",
        canonical_url=f"https://reddit.com/{external_id}",
    )


def test_cross_run_filter_excludes_existing_id_and_content(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    first_run = repository.create_run("first")
    repository.save_source_items(
        first_run.run_id,
        [
            _item("existing-id", "Existing body"),
            _item("existing-content", "Repeated content"),
        ],
    )

    result = filter_cross_run_duplicates(
        database,
        [
            _item("existing-id", "Changed body"),
            _item("new-id-same-content", "Repeated content"),
            _item("novel-id", "Completely new evidence"),
        ],
    )

    assert [item.external_id for item in result.items] == ["novel-id"]
    assert result.excluded_external_ids == 1
    assert result.excluded_content_hashes == 1


def test_cross_run_filter_deduplicates_new_batch(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    SQLiteResearchRepository(database).initialize()

    result = filter_cross_run_duplicates(
        database,
        [
            _item("one", "Same new content"),
            _item("two", "Same new content"),
            _item("one", "Different content"),
        ],
    )

    assert [item.external_id for item in result.items] == ["one"]
    assert result.excluded_external_ids == 1
    assert result.excluded_content_hashes == 1
