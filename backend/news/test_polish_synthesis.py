from unittest import mock

from django.test import SimpleTestCase

from news import clinic_council
from news.clinic_ai import ClinicAIError


class PolishLinesTests(SimpleTestCase):
    def test_accepts_language_fix_within_limits(self):
        fixed = {'lines': ['13-latek planował zamach w szkole, w plecaku miał 30-centymetrowy nóż.',
                           'Policja potwierdziła, że chłopiec planował atak w szkole.']}
        with mock.patch.object(clinic_council, 'ask_role', return_value=(fixed, 'bielik')):
            result = clinic_council.polish_lines(
                ['13-letni planował zamach w szkole, w plecaku miał 30-cm nóż.',
                 'Policja potwierdziła, że 13-letni planował atak w szkole.'], [120, 200])
        self.assertEqual(result, fixed['lines'])

    def test_keeps_original_when_too_long_wrong_count_or_error(self):
        lines = ['Krótka linia po polsku o diagnozie.', 'Druga linia po polsku o źródłach.']
        with mock.patch.object(clinic_council, 'ask_role', return_value=({'lines': ['x' * 300, lines[1]]}, 'm')):
            self.assertEqual(clinic_council.polish_lines(lines, [60, 60]), lines)
        with mock.patch.object(clinic_council, 'ask_role', return_value=({'lines': [lines[0]]}, 'm')):
            self.assertEqual(clinic_council.polish_lines(lines, [60, 60]), lines)
        with mock.patch.object(clinic_council, 'ask_role', side_effect=ClinicAIError('down')):
            self.assertEqual(clinic_council.polish_lines(lines, [60, 60]), lines)
