import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import shutil

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.file_organizer.organizer import FileOrganizer, UserAbort

class TestFileOrganizerInteractive(unittest.TestCase):
    def setUp(self):
        self.source_dir = Path("test_interactive_dir")
        self.source_dir.mkdir(exist_ok=True)
        
        # Create dummy files
        self.file1 = self.source_dir / "test1.txt"
        self.file1.touch()
        self.file2 = self.source_dir / "test2.jpg"
        self.file2.touch()
        
        self.organizer = FileOrganizer(source_dir=self.source_dir, interactive=True, dry_run=True)

    def tearDown(self):
        shutil.rmtree(self.source_dir)

    @patch('builtins.input')
    def test_interactive_yes(self, mock_input):
        """Test confirming a move with 'y'."""
        mock_input.side_effect = ['y']
        
        # Category for txt is Documents
        category = self.organizer._prompt_user(self.file1, "Documents")
        self.assertEqual(category, "Documents")

    @patch('builtins.input')
    def test_interactive_no(self, mock_input):
        """Test skipping a move with 'n'."""
        mock_input.side_effect = ['n']
        
        category = self.organizer._prompt_user(self.file1, "Documents")
        self.assertIsNone(category)

    @patch('builtins.input')
    def test_interactive_all(self, mock_input):
        """Test 'all' option disabling interactive mode."""
        mock_input.side_effect = ['a']
        
        self.assertTrue(self.organizer.interactive)
        category = self.organizer._prompt_user(self.file1, "Documents")
        
        self.assertEqual(category, "Documents")
        self.assertFalse(self.organizer.interactive)

    @patch('builtins.input')
    def test_interactive_quit(self, mock_input):
        """Test 'quit' option raising UserAbort."""
        mock_input.side_effect = ['q']
        
        with self.assertRaises(UserAbort):
            self.organizer._prompt_user(self.file1, "Documents")

    @patch('builtins.input')
    def test_interactive_change_category(self, mock_input):
        """Test changing category on the fly."""
        # First input 'c', second input 'Archives'
        mock_input.side_effect = ['c', 'Archives']
        
        category = self.organizer._prompt_user(self.file1, "Documents")
        self.assertEqual(category, "Archives")

    @patch('builtins.input')
    def test_interactive_invalid_input(self, mock_input):
        """Test invalid input followed by valid input."""
        # First input invalid, second 'y'
        mock_input.side_effect = ['invalid', 'y']
        
        category = self.organizer._prompt_user(self.file1, "Documents")
        self.assertEqual(category, "Documents")
        self.assertEqual(mock_input.call_count, 2)

    @patch('builtins.input')
    def test_interactive_empty_input(self, mock_input):
        """Test empty input (should be invalid/retry, not default to yes)."""
        # Empty input should not return, next input 'y' should work
        mock_input.side_effect = ['', 'y']
        
        category = self.organizer._prompt_user(self.file1, "Documents")
        self.assertEqual(category, "Documents")
        self.assertEqual(mock_input.call_count, 2)

if __name__ == '__main__':
    unittest.main()
