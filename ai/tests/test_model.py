import unittest

from ai.model import read_json


class TestReadJson(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(read_json('{"requirements": []}'), {"requirements": []})

    def test_json_inside_code_block(self):
        reply = 'Here is the result:\n```json\n{"requirements": []}\n```'
        self.assertEqual(read_json(reply), {"requirements": []})

    def test_refusal_raises_value_error(self):
        with self.assertRaises(ValueError):
            read_json("Sorry, I can't")
