import json
import unittest
from pathlib import Path

from ai.guardrails.classify import check_recommendation, classify

CASES = Path(__file__).resolve().parents[1] / "fixtures" / "adversarial" / "cases.json"
MOCKS = CASES.parent.parent / "mock_responses"
RESUMES = CASES.parent.parent / "resumes"


class TestAdversarialCases(unittest.TestCase):
    def test_every_case(self):
        for case in json.loads(CASES.read_text(encoding="utf-8")):
            with self.subTest(case["name"]):
                status = classify(case["suggestion"], case["source"], case.get("evidence", ""))["status"]
                # Skip only the documented wrong label, never an arbitrary new failure.
                if status == case.get("known_status"):
                    self.skipTest(f"known gap: {case['known_gap']} (got {status})")
                self.assertEqual(status, case["expected"])


class TestClassify(unittest.TestCase):
    def test_invented_quantities_keep_their_units(self):
        for suggestion, source in (
            ("Served 5k users", "Served 5 users"),
            ("Served 5 million users", "Served 5 users"),
            ("Raised $5M", "Raised $5"),
            ("Made a query 10x faster", "Made a query for 10 users"),
            ("Increased attendance by 40 percent", "Hosted 40 students"),
            ("Fixed dozens of bugs", "Fixed bugs"),
            ("Worked with a team of ten", "Worked with a team of 3"),
            ("Cut time by .5 seconds", "Cut time by 5 seconds"),
            ("Cut time by 40%", "Cut time by 20% to 40%"),
            ("Cut time by 40%", "Cut time by between 20 and 40%"),
        ):
            with self.subTest(suggestion=suggestion):
                self.assertEqual(classify(suggestion, source)["status"], "unsupported")

    def test_equivalent_amount_formats_are_supported(self):
        for suggestion, source in (("Raised $2000", "Raised $2,000"),
                                   ("Served 5000 users", "Served 5k users"),
                                   ("Worked with 25 people", "Worked with twenty-five people")):
            with self.subTest(suggestion=suggestion):
                self.assertEqual(classify(suggestion, source)["status"], "supported")

    def test_known_tool_names_are_caught_in_any_position(self):
        for tool in ("pulumi", "helm", "kubectl", "iOS", "jQuery", "Salesforce", "Dockerized", "C++"):
            for suggestion in (f"{tool} used for the app", f"Built the app with {tool}"):
                with self.subTest(suggestion=suggestion):
                    self.assertEqual(classify(suggestion, "Built the app with C#")["status"],
                                     "unsupported")

    def test_invented_titles_need_resume_or_user_note(self):
        source = "Intern at the campus office"
        for suggestion in ("Supervisor at the campus office", "worked as software engineer"):
            with self.subTest(suggestion=suggestion):
                self.assertEqual(classify(suggestion, source)["status"], "unsupported")
        self.assertEqual(classify("Engineer at the campus office", source,
                                  "I was an engineer there")["status"], "needs_confirmation")

    def test_unknown_mixed_case_name_at_sentence_start(self):
        for suggestion in ("NebulaDB used for the app", "Used nebulaDB for the app"):
            with self.subTest(suggestion=suggestion):
                self.assertEqual(classify(suggestion, "Built the app")["status"],
                                 "needs_confirmation")

    def test_responsibility_forms_and_co_led_upgrade(self):
        for word in ("Lead", "Leading", "managing", "Oversaw", "Headed"):
            with self.subTest(word=word):
                self.assertEqual(classify(f"{word} the project", "Helped with the project")["status"],
                                 "needs_confirmation")
        self.assertEqual(classify("Led the project", "Co-led the project")["status"],
                         "needs_confirmation")

    def test_all_checks_use_pdf_cleanup(self):
        self.assertEqual(classify("Built with Docker", "Built with Doc\u200bker")["status"],
                         "supported")
        self.assertEqual(classify("Built with Docker", "Built the app", "Used Doc\u200bker")["status"],
                         "needs_confirmation")
        self.assertEqual(classify("Built\tNebulaDB", "Built the app")["status"],
                         "needs_confirmation")

    def test_each_resume_line_supports_itself(self):
        for resume in sorted(RESUMES.glob("*.txt")):
            for line in resume.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    with self.subTest(resume=resume.name, line=line):
                        self.assertEqual(classify(line, line)["status"], "supported")

    def test_multiword_aliases_support_their_original_text(self):
        for text in ("Built an AWS Lambda function", "Built Machine Learning models",
                     "Hosted the API on Amazon Web Services", "Hosted it on Google Cloud"):
            with self.subTest(text=text):
                self.assertEqual(classify(text, text), {"status": "supported", "reasons": []})

    def test_multiword_alias_rewrites_are_supported_in_both_directions(self):
        for first, second in (("Built on AWS Lambda", "Built on Amazon Web Services Lambda"),
                              ("Built Machine Learning models", "Built ML models"),
                              ("Built in Go", "Built in golang")):
            for suggestion, source in ((first, second), (second, first)):
                with self.subTest(suggestion=suggestion, source=source):
                    self.assertEqual(classify(suggestion, source)["status"], "supported")

    def test_reason_names_the_invented_number(self):
        result = classify("Cut costs by 40%", "Cut costs for the team.")
        self.assertEqual(result["status"], "unsupported")
        self.assertIn("40% is not in your resume", result["reasons"])

    def test_supported_has_no_reasons(self):
        self.assertEqual(classify("Built JS apps", "Built javascript apps"),
                         {"status": "supported", "reasons": []})

    def test_unknown_capitalized_name_in_a_lowercase_sentence(self):
        # A user's own edit may start lowercase; only the first word is skipped, never the first name.
        result = classify("deployed the scripts with NebulaDB", "Wrote Python scripts")
        self.assertEqual(result["status"], "needs_confirmation")

    def test_unsupported_beats_needs_confirmation(self):
        # "led" needs confirmation, the invented 40% is unsupported.
        result = classify("Led a 40% cut", "Helped cut costs")
        self.assertEqual(result["status"], "unsupported")
        # Unsupported reasons come first, and the confirm reasons are still reported.
        self.assertEqual(result["reasons"][0], "40% is not in your resume")
        self.assertIn("Your resume doesn't say 'led'", result["reasons"])

    def test_empty_suggestion_is_unsupported(self):
        for suggestion in ("", "   ", "...", " - \n"):
            with self.subTest(suggestion=suggestion):
                result = classify(suggestion, "Built a Python script for a campus club.")
                self.assertEqual(result["status"], "unsupported")
                self.assertEqual(result["reasons"], ["There is no suggestion to check"])

    def test_empty_source_needs_a_note(self):
        for source in ("", " \n", "-"):
            with self.subTest(source=source):
                self.assertEqual(classify("Built a small script", source)["status"], "unsupported")
                self.assertEqual(classify("Built a small script", source, "I built a small script")["status"],
                                 "needs_confirmation")

    def test_time_unit_changed_or_added_is_unsupported(self):
        for suggestion, source in (("Saved 5 hours a day", "Saved 5 hours a week"),
                                   ("Ran a daily tutoring session", "Ran a tutoring session"),
                                   ("Ran a weekly tutoring session", "Ran a monthly tutoring session")):
            with self.subTest(suggestion=suggestion):
                self.assertEqual(classify(suggestion, source)["status"], "unsupported")

    def test_time_unit_only_in_note_needs_confirmation(self):
        result = classify("Ran a daily tutoring session", "Ran a tutoring session", "It met every day")
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertIn("day is only in your note", result["reasons"])

    def test_weekly_and_a_week_are_the_same_unit(self):
        self.assertEqual(classify("Ran a weekly tutoring session", "Ran a tutoring session once a week")["status"],
                         "supported")

    def test_invented_outcome_with_a_less_common_verb(self):
        self.assertEqual(classify("Automated weekly report generation, slashing manual processing time",
                                  "Automated weekly report generation")["status"], "unsupported")

    def test_invented_outcome_is_unsupported(self):
        result = classify("Built a script, which increased club attendance", "Built a script for a club")
        self.assertEqual(result["status"], "unsupported")
        self.assertIn("Your resume doesn't mention a result like 'increase'", result["reasons"])

    def test_outcome_only_in_note_needs_confirmation(self):
        result = classify("Built a script, which increased club attendance", "Built a script for a club",
                          "Attendance went up and we grew")
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertIn("The result is only in your note", result["reasons"])

    def test_reworded_outcome_is_supported(self):
        self.assertEqual(classify("Saved 5 hours of manual work a week", "Cutting manual work by 5 hours a week")["status"],
                         "supported")

    def test_mostly_new_wording_needs_confirmation(self):
        result = classify("Organized a charity gala for local families.",
                          "Built a Python script to email weekly reminders for a campus club.")
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertIn("Most of this wording isn't in your resume", result["reasons"])


    def test_hyphenated_time_units_count(self):
        self.assertEqual(classify("Ran hour-long tutoring sessions for students",
                                  "Ran tutoring sessions for students")["status"], "unsupported")
        self.assertEqual(classify("Ran tutoring sessions lasting an hour for students",
                                  "Ran hour-long tutoring sessions for students")["status"], "supported")

    def test_short_and_small_time_units(self):
        self.assertEqual(classify("Reduced API response time to 5 milliseconds",
                                  "Reduced API response time to 5 seconds")["status"], "unsupported")
        self.assertEqual(classify("Reduced API response time to 5 ms",
                                  "Reduced API response time to 5 seconds")["status"], "unsupported")
        self.assertEqual(classify("Saved 5 minutes per report", "Saved 5 min per report")["status"],
                         "supported")
        self.assertEqual(classify("Tutored students for 5 hours weekly",
                                  "Tutored students for 5 hrs weekly")["status"], "supported")

    def test_short_units_after_a_hyphen_or_a_number_word(self):
        self.assertEqual(classify("Processed API requests with 5-ms latency",
                                  "Processed API requests with 5-second latency")["status"], "unsupported")
        self.assertEqual(classify("Processed API requests in five ms",
                                  "Processed API requests in five seconds")["status"], "unsupported")
        for short, long in (("five sec", "five seconds"), ("five min", "five minutes")):
            with self.subTest(short=short):
                self.assertEqual(classify(f"Processed API requests in {long}",
                                          f"Processed API requests in {short}")["status"], "supported")

    def test_hyphenated_title_is_its_own_claim(self):
        self.assertEqual(classify("Built a student software project as co-founder",
                                  "Built a student software project")["status"], "unsupported")
        # "Co-founder" doesn't back "Founder": that drops the shared credit.
        self.assertEqual(classify("Founder of the campus coding club",
                                  "Co-founder of the campus coding club")["status"], "unsupported")

    def test_hyphenated_outcome_and_the_noun_results(self):
        self.assertEqual(classify("Built a cost-saving report automation script",
                                  "Built a report automation script")["status"], "unsupported")
        self.assertEqual(classify("Built a dashboard showing test results",
                                  "Built a dashboard showing test output")["status"], "supported")

    def test_dropping_helped_needs_confirmation(self):
        result = classify("Migrated weekly reports from Excel to SQL.",
                          "Helped migrate weekly reports from Excel to SQL.")
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertIn("Your resume says you helped; this drops that", result["reasons"])
        # A "help desk" left in the sentence doesn't hide the dropped "Helped".
        self.assertEqual(classify("Migrated help desk reports from Excel to SQL",
                                  "Helped migrate help desk reports from Excel to SQL")["status"],
                         "needs_confirmation")
        self.assertEqual(classify("Helped move weekly reports from Excel to SQL.",
                                  "Helped migrate weekly reports from Excel to SQL.")["status"], "supported")


class TestCheckRecommendation(unittest.TestCase):
    ALEX = (RESUMES / "alex.txt").read_text(encoding="utf-8")
    BULLET = "Documented the report steps so new student workers could run them alone."
    OTHER = "Wrote 25 unit tests for the planning rules using pytest."

    def quote(self, text, source="resume"):
        start = self.ALEX.index(text)
        return {"source": source, "start": start, "end": start + len(text), "text": text}

    def rec(self, suggestion, evidence, bullet=BULLET):
        return {"original_bullet": bullet, "suggestion": suggestion, "evidence": evidence}

    def test_contract_mock_answers_get_their_label(self):
        for name in ("supported", "needs_confirmation", "unsupported", "missing"):
            mock = json.loads((MOCKS / f"{name}.json").read_text(encoding="utf-8"))
            for rec in mock["recommendations"]:
                with self.subTest(mock=name):
                    self.assertEqual(check_recommendation(rec, mock["resume_text"])["status"], rec["status"])

    def test_fact_from_another_bullet_does_not_back_this_one(self):
        suggestion = "Documented the report steps so 25 new student workers could run them alone."
        result = check_recommendation(self.rec(suggestion, [self.quote(self.BULLET)]), self.ALEX)
        self.assertEqual(result["status"], "unsupported")
        self.assertIn("25 is not in your resume", result["reasons"])
        # Once the model cites the other bullet at its real position, the number has a source.
        # The words are all there, so the rules call it supported; a meaning check would not.
        both = [self.quote(self.BULLET), self.quote(self.OTHER)]
        self.assertEqual(check_recommendation(self.rec(suggestion, both), self.ALEX)["status"], "supported")

    def test_quote_with_wrong_positions_is_ignored(self):
        suggestion = "Documented the report steps so 25 new student workers could run them alone."
        wrong = dict(self.quote(self.OTHER), start=0, end=len(self.OTHER))
        result = check_recommendation(self.rec(suggestion, [self.quote(self.BULLET), wrong]), self.ALEX)
        self.assertEqual(result["status"], "unsupported")

    def test_original_bullet_not_in_resume_is_ignored(self):
        rec = self.rec("Documented the report steps", [], bullet="Documented the report steps for Contoso.")
        self.assertEqual(check_recommendation(rec, self.ALEX)["status"], "unsupported")

    def test_only_a_user_note_needs_confirmation(self):
        suggestion = "Documented the report steps so 25 new student workers could run them alone."
        note = {"source": "evidence", "text": "I trained 25 workers"}
        result = check_recommendation(self.rec(suggestion, [self.quote(self.BULLET), note]), self.ALEX)
        self.assertEqual(result["status"], "needs_confirmation")

    def test_a_quoted_fragment_is_read_with_its_whole_line(self):
        # The model may quote part of a line; the words it left out still count.
        fragment = "migrate weekly reports from Excel to SQL."
        suggestion = "Migrated weekly reports from Excel to SQL."
        for rec in (self.rec(suggestion, [self.quote(fragment)], bullet=""), self.rec(suggestion, [], bullet=fragment)):
            with self.subTest(rec=rec):
                self.assertEqual(check_recommendation(rec, self.ALEX)["status"], "needs_confirmation")
        resume = "- Co-founder of the NHSU robotics club\n- Handled between 3k and 5k requests per day\n"
        for bullet, suggestion in (("founder of the NHSU robotics club", "Founder of the NHSU robotics club"),
                                   ("5k requests per day", "Handled 5k requests per day")):
            with self.subTest(bullet=bullet):
                self.assertEqual(check_recommendation(self.rec(suggestion, [], bullet), resume)["status"],
                                 "unsupported")

    def test_a_quote_ending_or_starting_at_a_line_break_stays_on_its_line(self):
        resume = "- Helped migrate reports to SQL\n- Wrote 25 unit tests\n- Helped write docs\n"
        for text in ("Wrote 25 unit tests\n", "\n- Wrote 25 unit tests"):
            start = resume.index(text)
            quote = {"source": "resume", "start": start, "end": start + len(text), "text": text}
            with self.subTest(text=text):
                rec = self.rec("Wrote 25 unit tests", [quote], bullet="")
                self.assertEqual(check_recommendation(rec, resume)["status"], "supported")

    def test_windows_line_breaks_and_blank_quotes(self):
        resume = "- Wrote 25 unit tests\r\n- Documented report steps\r\n- Helped migrate weekly reports"
        for text in ("\r\n- Documented report steps", "Documented report steps\r\n", "\r\n"):
            start = resume.index(text)
            quote = {"source": "resume", "start": start, "end": start + len(text), "text": text}
            with self.subTest(text=text):
                rec = self.rec("Documented 25 report steps", [quote], bullet="")
                self.assertEqual(check_recommendation(rec, resume)["status"], "unsupported")
        # A quote that is only a space inside a line backs nothing, not that whole line.
        space = resume.index(" unit")
        blank = {"source": "resume", "start": space, "end": space + 1, "text": " "}
        rec = self.rec("Wrote 25 unit tests", [blank], bullet="")
        self.assertEqual(check_recommendation(rec, resume)["status"], "unsupported")

    def test_wrapped_bullet_is_found_without_taking_its_neighbors(self):
        wrapped = ("- Rebuilt the order form in React and cut page load time by 30% by compressing\n"
                   "images and splitting code.\n- Wrote 25 unit tests\n")
        bullet = "Rebuilt the order form in React and cut page load time by 30% by compressing images and splitting code."
        self.assertEqual(check_recommendation(self.rec(bullet, [], bullet), wrapped)["status"], "supported")
        # Without bullet markers, a line is still its own bullet first: "Helped" above it doesn't count.
        plain = "Helped migrate reports to SQL\nWrote 25 unit tests\n"
        rec = self.rec("Wrote 25 unit tests", [], "Wrote 25 unit tests")
        self.assertEqual(check_recommendation(rec, plain)["status"], "supported")
        # A "bullet" stitched across two real bullets is not in the resume.
        stitched = self.rec("Wrote 25 unit tests and migrated reports to SQL", [],
                            "Wrote 25 unit tests - Helped migrate reports to SQL")
        resume = "- Wrote 25 unit tests\n- Helped migrate reports to SQL\n"
        self.assertEqual(check_recommendation(stitched, resume)["status"], "unsupported")

    def test_malformed_model_output_is_never_supported(self):
        # Bad model output must fail closed, not crash and not pass.
        good = self.rec(self.BULLET, [self.quote(self.BULLET)])
        self.assertEqual(check_recommendation(good, self.ALEX)["status"], "supported")
        bad_quote = dict(self.quote(self.BULLET), start=True)
        junk = [None, "x", {"source": "evidence"}, {"source": "evidence", "text": 5}, bad_quote]
        # Junk evidence is skipped; the real bullet still backs the suggestion.
        self.assertEqual(check_recommendation(dict(good, evidence=junk), self.ALEX)["status"], "supported")
        for change in ({"suggestion": None}, {"suggestion": 5}, {"original_bullet": None, "evidence": None},
                       {"original_bullet": "", "evidence": junk}):
            rec = {k: v for k, v in good.items()}
            rec.update(change)
            with self.subTest(change=str(change)):
                self.assertNotEqual(check_recommendation(rec, self.ALEX)["status"], "supported")
        missing = {k: v for k, v in good.items() if k != "suggestion"}
        self.assertEqual(check_recommendation(missing, self.ALEX)["status"], "unsupported")
        self.assertEqual(check_recommendation(good, None)["status"], "unsupported")
        for rec in (None, "text", [], 5):
            with self.subTest(rec=repr(rec)):
                self.assertEqual(check_recommendation(rec, self.ALEX)["status"], "unsupported")


if __name__ == "__main__":
    unittest.main()
