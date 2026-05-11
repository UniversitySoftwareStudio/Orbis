import json

from agents.submission_agent import evaluate_submission


def test_submission_agent_approves_relevant_text_submission():
    def fake_llm(prompt: str) -> str:
        assert "Line-by-line review JSON" in prompt
        assert "merge sort" in prompt.lower()
        return json.dumps(
            {
                "decision": "approved",
                "confidence": 0.91,
                "reason": "The file is a real attempt at the requested merge sort assignment.",
                "assignment_understanding": "Implement and explain merge sort.",
                "submission_summary": "Python implementation and notes about merge sort complexity.",
                "evidence": [{"line": 1, "quote": "merge_sort", "why_it_matters": "Matches the task."}],
                "missing_requirements": [],
                "flags": [],
            }
        )

    result = evaluate_submission(
        assignment_title="Merge sort implementation",
        assignment_description="Submit Python code and a short explanation of merge sort complexity.",
        content=b"def merge_sort(values):\n    return values\n\n# Complexity: O(n log n)\n",
        filename="solution.py",
        content_type="text/x-python",
        llm_complete=fake_llm,
    )

    assert result.decision == "approved"
    assert result.confidence == 0.91
    assert result.report["file"]["line_count"] == 4
    assert result.report["line_review"]["term_hit_counts"]["merge"] >= 1


def test_submission_agent_rejects_irrelevant_text_submission():
    def fake_llm(prompt: str) -> str:
        assert "linear algebra" in prompt.lower()
        return json.dumps(
            {
                "decision": "rejected",
                "confidence": 0.88,
                "reason": "The file discusses vacation plans instead of the requested linear algebra work.",
                "assignment_understanding": "Solve linear algebra exercises.",
                "submission_summary": "A personal note about travel.",
                "evidence": [{"line": 1, "quote": "vacation", "why_it_matters": "Unrelated topic."}],
                "missing_requirements": ["No matrix or vector work is present."],
                "flags": ["unrelated_content"],
            }
        )

    result = evaluate_submission(
        assignment_title="Linear algebra problem set",
        assignment_description="Submit solutions for matrix multiplication and eigenvalue exercises.",
        content=b"My vacation plan is to visit the seaside this summer.\n",
        filename="notes.txt",
        content_type="text/plain",
        llm_complete=fake_llm,
    )

    assert result.decision == "rejected"
    assert result.feedback.startswith("REJECTED:")
    assert result.report["llm"]["parsed"]["missing_requirements"]


def test_submission_agent_rejects_empty_file_before_llm():
    called = False

    def fake_llm(_: str) -> str:
        nonlocal called
        called = True
        return "{}"

    result = evaluate_submission(
        assignment_title="Any assignment",
        assignment_description="Any description",
        content=b"",
        filename="empty.txt",
        content_type="text/plain",
        llm_complete=fake_llm,
    )

    assert result.decision == "rejected"
    assert "file is empty" in result.feedback
    assert called is False
