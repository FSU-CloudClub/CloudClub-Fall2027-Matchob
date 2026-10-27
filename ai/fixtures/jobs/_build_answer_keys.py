"""Build hand-labeled answer keys for the 10 job postings (Lane 4).

Each requirement below is labeled BY HAND: a human chose the exact text to
pull from the posting, its category (skill / tool / experience / responsibility)
and its priority (must / nice). This script only does the mechanical part -
finding the exact character offsets of each chosen phrase in the posting file -
so that every source_span matches the posting byte-for-byte and validates
against contracts/requirement.schema.json.

Run from the repo root:  python ai/fixtures/jobs/_build_answer_keys.py
It writes job-XX-*.key.json next to each posting.
"""

import json
from pathlib import Path

JOBS = Path(__file__).parent

# For each posting: the exact phrase to highlight, its category and priority.
# category: skill | tool | experience | responsibility
# priority: must (Requirements section) | nice (Nice to have section)
LABELS = {
    "job-01-frontend-intern.txt": [
        ("building user interfaces with React", "skill", "must"),
        ("write clean, readable JavaScript", "skill", "must"),
        ("using Git for version control", "tool", "must"),
        ("Strong communication skills when working on a team", "skill", "must"),
        ("Experience with TypeScript", "skill", "nice"),
        ("testing tools like Jest", "tool", "nice"),
        ("exposure to accessibility best practices", "skill", "nice"),
    ],
    "job-02-backend-intern.txt": [
        ("writing REST APIs in Python", "skill", "must"),
        ("working with relational databases like PostgreSQL", "tool", "must"),
        ("write unit tests for your code", "skill", "must"),
        ("using Git and pull requests", "tool", "must"),
        ("Familiarity with Docker", "tool", "nice"),
        ("Exposure to AWS or another cloud provider", "tool", "nice"),
        ("Experience with FastAPI or Flask", "tool", "nice"),
    ],
    "job-03-data-analyst.txt": [
        ("Strong SQL skills for querying large datasets", "skill", "must"),
        ("building dashboards in Tableau", "tool", "must"),
        ("clean and prepare messy data in Excel", "skill", "must"),
        ("Clear written communication for reporting findings", "skill", "must"),
        ("Experience with Python for data analysis", "skill", "nice"),
        ("Familiarity with statistics and A/B testing", "skill", "nice"),
        ("Exposure to Google BigQuery", "tool", "nice"),
    ],
    "job-04-fullstack.txt": [
        ("2+ years of experience building web applications", "experience", "must"),
        ("Proficiency with React on the frontend", "skill", "must"),
        ("writing backend services in Node.js", "skill", "must"),
        ("designing and querying SQL databases", "skill", "must"),
        ("Experience with Git-based team workflows", "tool", "must"),
        ("deploying applications with Docker", "tool", "nice"),
        ("Familiarity with CI/CD pipelines", "tool", "nice"),
        ("Exposure to GraphQL", "tool", "nice"),
    ],
    "job-05-devops.txt": [
        ("3+ years of experience operating production systems on Linux", "experience", "must"),
        ("Strong experience with AWS services", "tool", "must"),
        ("building CI/CD pipelines", "skill", "must"),
        ("writing automation scripts in Python or Bash", "skill", "must"),
        ("infrastructure as code using Terraform", "tool", "must"),
        ("Experience with Kubernetes in production", "tool", "nice"),
        ("monitoring tools like Prometheus", "tool", "nice"),
        ("Exposure to Go", "skill", "nice"),
    ],
    "job-06-ml-engineer.txt": [
        ("Strong Python skills for building ML pipelines", "skill", "must"),
        ("training models with PyTorch or TensorFlow", "tool", "must"),
        ("understanding of machine learning fundamentals", "skill", "must"),
        ("deploying models as production services", "experience", "must"),
        ("working with large datasets", "skill", "must"),
        ("Experience with MLflow for experiment tracking", "tool", "nice"),
        ("Familiarity with Docker and Kubernetes", "tool", "nice"),
        ("cloud GPUs on AWS or GCP", "tool", "nice"),
    ],
    "job-07-qa-automation.txt": [
        ("writing automated tests in Python", "skill", "must"),
        ("Selenium for browser testing", "tool", "must"),
        ("Understanding of REST API testing", "skill", "must"),
        ("working in a CI/CD pipeline", "tool", "must"),
        ("Attention to detail when reproducing bugs", "skill", "must"),
        ("Experience with performance testing tools", "tool", "nice"),
        ("Familiarity with Docker", "tool", "nice"),
        ("Exposure to mobile test automation", "skill", "nice"),
    ],
    "job-08-mobile-ios.txt": [
        ("2+ years building iOS apps with Swift", "experience", "must"),
        ("UIKit or SwiftUI frameworks", "tool", "must"),
        ("consuming REST APIs from a mobile client", "skill", "must"),
        ("shipping apps to the App Store", "experience", "must"),
        ("write unit tests with XCTest", "tool", "must"),
        ("Familiarity with Core Data", "tool", "nice"),
        ("Experience with Combine", "tool", "nice"),
        ("Exposure to accessibility on iOS", "skill", "nice"),
    ],
    "job-09-security-analyst.txt": [
        ("3+ years of experience in information security", "experience", "must"),
        ("understanding of common web vulnerabilities", "skill", "must"),
        ("security monitoring and SIEM tools", "tool", "must"),
        ("write scripts in Python to automate checks", "skill", "must"),
        ("Clear communication when writing incident reports", "skill", "must"),
        ("certification such as CISSP or Security+", "experience", "nice"),
        ("cloud security on AWS", "tool", "nice"),
        ("Familiarity with penetration testing", "skill", "nice"),
    ],
    "job-10-sre.txt": [
        ("4+ years running large-scale production systems", "experience", "must"),
        ("Deep experience with Linux and networking", "skill", "must"),
        ("Experience with Kubernetes in production", "tool", "must"),
        ("writing automation in Python or Go", "skill", "must"),
        ("defining SLOs and monitoring reliability", "responsibility", "must"),
        ("Experience with Terraform", "tool", "nice"),
        ("Familiarity with distributed tracing", "skill", "nice"),
        ("Exposure to incident command processes", "responsibility", "nice"),
    ],
}


def build():
    for filename, labels in LABELS.items():
        job_path = JOBS / filename
        job_text = job_path.read_text()
        requirements = []
        search_from = 0
        for i, (phrase, category, priority) in enumerate(labels, start=1):
            start = job_text.find(phrase, search_from)
            if start == -1:
                # fall back to a global search so ordering mistakes are loud
                start = job_text.find(phrase)
            if start == -1:
                raise ValueError(
                    f"{filename}: phrase not found in posting: {phrase!r}"
                )
            end = start + len(phrase)
            search_from = end
            requirements.append({
                "id": f"req-{i}",
                "text": phrase,
                "category": category,
                "priority": priority,
                "source_span": {
                    "start": start,
                    "end": end,
                    "text": job_text[start:end],
                },
            })
        out = {
            "_comment": (
                "Hand-labeled answer key for " + filename + ". Each requirement's "
                "source_span is a character range into the posting text; "
                "job_text[start:end] equals text. Labeled by hand; offsets "
                "computed by _build_answer_keys.py."
            ),
            "job_file": filename,
            "job_text": job_text,
            "requirements": requirements,
        }
        key_path = JOBS / filename.replace(".txt", ".key.json")
        key_path.write_text(json.dumps(out, indent=2) + "\n")
        print(f"wrote {key_path.name}: {len(requirements)} requirements")


if __name__ == "__main__":
    build()
