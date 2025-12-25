"""Tests for File Organizer undo/rollback functionality."""
import tempfile
import json
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.file_organizer.organizer import FileOrganizer


@pytest.fixture
def temp_dir_with_files():
    """Create temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create test files
        (base / "photo.jpg").write_text("image content")
        (base / "document.pdf").write_text("pdf content")
        (base / "script.py").write_text("python content")

        yield base


@pytest.fixture
def temp_manifest_dir():
    """Create temporary directory for manifests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestManifestSaving:
    """Tests for manifest save functionality."""

    def test_manifest_created_after_organize(self, temp_dir_with_files, temp_manifest_dir):
        """Test that manifest file is created after organizing."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        manifests = list(temp_manifest_dir.glob("organize_*.json"))
        assert len(manifests) == 1

    def test_manifest_not_created_in_dry_run(self, temp_dir_with_files, temp_manifest_dir):
        """Test that manifest is not created in dry-run mode."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            dry_run=True,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        manifests = list(temp_manifest_dir.glob("organize_*.json"))
        assert len(manifests) == 0

    def test_manifest_content_structure(self, temp_dir_with_files, temp_manifest_dir):
        """Test that manifest contains required fields."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        manifest_path = list(temp_manifest_dir.glob("organize_*.json"))[0]
        with open(manifest_path, 'r') as f:
            data = json.load(f)

        assert "timestamp" in data
        assert "source_dir" in data
        assert "moves" in data
        assert "files_moved" in data
        assert len(data["moves"]) == 3  # 3 files organized


class TestUndoFunctionality:
    """Tests for undo/rollback functionality."""

    def test_undo_restores_files(self, temp_dir_with_files, temp_manifest_dir):
        """Test that undo restores files to original locations."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        # Verify files were moved
        assert not (temp_dir_with_files / "photo.jpg").exists()
        assert (temp_dir_with_files / "Images" / "photo.jpg").exists()

        # Undo
        undo_organizer = FileOrganizer(manifest_dir=temp_manifest_dir)
        result = undo_organizer.undo()

        # Verify files restored
        assert result["restored"] == 3
        assert (temp_dir_with_files / "photo.jpg").exists()
        assert (temp_dir_with_files / "document.pdf").exists()
        assert (temp_dir_with_files / "script.py").exists()

    def test_undo_removes_empty_directories(self, temp_dir_with_files, temp_manifest_dir):
        """Test that undo removes empty category directories."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        # Verify category dirs exist
        assert (temp_dir_with_files / "Images").exists()

        # Undo
        undo_organizer = FileOrganizer(manifest_dir=temp_manifest_dir)
        undo_organizer.undo()

        # Verify category dirs removed
        assert not (temp_dir_with_files / "Images").exists()

    def test_undo_removes_manifest_on_success(self, temp_dir_with_files, temp_manifest_dir):
        """Test that manifest is removed after successful undo."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        assert len(list(temp_manifest_dir.glob("organize_*.json"))) == 1

        undo_organizer = FileOrganizer(manifest_dir=temp_manifest_dir)
        undo_organizer.undo()

        assert len(list(temp_manifest_dir.glob("organize_*.json"))) == 0

    def test_undo_handles_missing_files(self, temp_dir_with_files, temp_manifest_dir):
        """Test that undo handles missing destination files gracefully."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        # Delete one organized file
        (temp_dir_with_files / "Images" / "photo.jpg").unlink()

        undo_organizer = FileOrganizer(manifest_dir=temp_manifest_dir)
        result = undo_organizer.undo()

        assert result["skipped"] == 1
        assert result["restored"] == 2

    def test_undo_no_manifest_returns_error(self, temp_manifest_dir):
        """Test that undo returns error when no manifest exists."""
        organizer = FileOrganizer(manifest_dir=temp_manifest_dir)
        result = organizer.undo()

        assert "error" in result


class TestListHistory:
    """Tests for list_history functionality."""

    def test_list_history_empty(self, temp_manifest_dir):
        """Test list_history with no manifests."""
        organizer = FileOrganizer(manifest_dir=temp_manifest_dir)
        history = organizer.list_history()
        assert history == []

    def test_list_history_with_manifests(self, temp_dir_with_files, temp_manifest_dir):
        """Test list_history shows manifest info."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        list_organizer = FileOrganizer(manifest_dir=temp_manifest_dir)
        history = list_organizer.list_history()

        assert len(history) == 1
        assert "filename" in history[0]
        assert "timestamp" in history[0]
        assert "source_dir" in history[0]
        assert history[0]["files_moved"] == 3


class TestLoadManifest:
    """Tests for manifest loading."""

    def test_load_most_recent_manifest(self, temp_dir_with_files, temp_manifest_dir):
        """Test that most recent manifest is loaded by default."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        loader = FileOrganizer(manifest_dir=temp_manifest_dir)
        manifest = loader._load_manifest()

        assert manifest is not None
        assert "moves" in manifest
        assert len(manifest["moves"]) == 3

    def test_load_specific_manifest(self, temp_dir_with_files, temp_manifest_dir):
        """Test loading a specific manifest file."""
        organizer = FileOrganizer(
            source_dir=temp_dir_with_files,
            manifest_dir=temp_manifest_dir
        )
        organizer.organize()

        manifest_file = list(temp_manifest_dir.glob("organize_*.json"))[0]
        loader = FileOrganizer(manifest_dir=temp_manifest_dir)
        manifest = loader._load_manifest(manifest_file)

        assert manifest is not None
        assert manifest["files_moved"] == 3

    def test_load_nonexistent_manifest_returns_none(self, temp_manifest_dir):
        """Test that loading nonexistent manifest returns None."""
        loader = FileOrganizer(manifest_dir=temp_manifest_dir)
        manifest = loader._load_manifest(Path("/nonexistent/path.json"))

        assert manifest is None
