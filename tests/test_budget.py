"""The manually typed site includes Python, SQL, templates, CSS, JS and requirements."""
import unittest
from pathlib import Path


class SourceBudgetTest(unittest.TestCase):
    def test_site_stays_within_twelve_thousand_characters(self):
        root = Path(__file__).resolve().parents[1]
        files = list(root.glob('*.py')) + list((root/'rental').glob('*.py')) + [root/'requirements.txt']
        files += list((root/'templates').glob('*.html'))
        files += list((root/'static').glob('*.css')) + list((root/'static').glob('*.js'))
        count = sum(len(path.read_text(encoding='utf-8')) for path in files)
        self.assertLessEqual(count, 12000, f'{count} Unicode characters with LF, including whitespace')
