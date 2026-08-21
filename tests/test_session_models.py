import unittest

from db.models import LearnedWord, WordRepetitionAnswer


class SessionModelTest(unittest.TestCase):
    def test_session_id_is_required_for_new_records(self):
        self.assertFalse(LearnedWord.__table__.c.session_id.nullable)
        self.assertFalse(WordRepetitionAnswer.__table__.c.session_id.nullable)
        self.assertFalse(
            WordRepetitionAnswer.__table__.c.answer_language.nullable,
        )
