import json

from app.services.question_generator import build_time_conversion_question, generate_with_llm, generate_with_template


def test_template_generator_does_not_use_generic_subtopic_explanation():
    question = generate_with_template("Simpan dan Labur", "easy")
    generic_explanation = (
        "Soalan ini "
        "dipilih supaya "
        "kemahiran Matematik Tahun 5 "
        "sepadan dengan subtopik."
    )

    assert generic_explanation not in question["explanation_ms"]


def test_template_generator_uses_step_by_step_explanation():
    question = generate_with_template("Simpan dan Labur", "easy")

    assert "Langkah 1" in question["explanation_ms"]
    assert "Langkah 2" in question["explanation_ms"]
    assert question["expected_answer"] in question["explanation_ms"]
    assert question["prompt_ms"].split(".")[0] in question["explanation_ms"]


def test_llm_generator_keeps_multilevel_hints(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "prompt_ms": "Aina menyimpan RM10 setiap bulan selama 3 bulan. Berapakah jumlah simpanannya?",
                                    "expected_answer": "RM30",
                                    "hint_ms": "Cari jumlah simpanan bulanan dan bilangan bulan.",
                                    "hint_level2_ms": "Darab RM10 dengan 3 bulan.",
                                    "hint_level3_ms": "10 x 3 = 30, jadi jumlahnya RM30.",
                                    "explanation_ms": "Langkah 1: Kenal pasti RM10 setiap bulan. Langkah 2: Darab 10 dengan 3. Langkah 3: Jawapan akhir ialah RM30.",
                                    "options": [],
                                }
                            )
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("app.services.question_generator.httpx.post", fake_post)

    question = generate_with_llm("Simpan dan Labur", "easy", "short_answer")

    assert question["source"] == "ai"
    assert question["hint_level2_ms"] == "Darab RM10 dengan 3 bulan."
    assert question["hint_level3_ms"] == "10 x 3 = 30, jadi jumlahnya RM30."
    assert "Langkah 1" in question["explanation_ms"]


def test_template_generator_uses_subtopic_specific_context():
    samples = [
        ("Simpan dan Labur", ["RM", "simpan"], ["pecahan", "1/"]),
        ("Tempoh", ["jam", "minit"], ["pecahan", "1/"]),
        ("Poligon Sekata", ["poligon", "sisi"], ["pecahan", "1/"]),
    ]

    for subtopic, expected_terms, forbidden_terms in samples:
        question = generate_with_template(subtopic, "medium")
        prompt = question["prompt_ms"].lower()
        assert any(term.lower() in prompt for term in expected_terms)
        assert not any(term.lower() in prompt for term in forbidden_terms)


def test_template_generator_has_clear_difficulty_progression():
    easy = generate_with_template("Simpan dan Labur", "easy")
    medium = generate_with_template("Simpan dan Labur", "medium")
    hard = generate_with_template("Simpan dan Labur", "hard")

    assert "setiap bulan" in easy["prompt_ms"]
    assert "mengeluarkan" in medium["prompt_ms"]
    assert "faedah" in hard["prompt_ms"]

    easy_time = generate_with_template("Tempoh", "easy")
    medium_time = generate_with_template("Tempoh", "medium")
    hard_time = generate_with_template("Tempoh", "hard")
    assert "dalam minit" in easy_time["prompt_ms"]
    assert "bermula" in medium_time["prompt_ms"]
    assert "dua aktiviti" in hard_time["prompt_ms"].lower()

    easy_polygon = generate_with_template("Poligon Sekata", "easy")
    medium_polygon = generate_with_template("Poligon Sekata", "medium")
    hard_polygon = generate_with_template("Poligon Sekata", "hard")
    assert "bilangan sisinya" in easy_polygon["prompt_ms"]
    assert "perimeter" in medium_polygon["prompt_ms"]
    assert "sudut pedalaman" in hard_polygon["prompt_ms"]


def test_template_generator_does_not_prefix_prompt_with_subtopic_title():
    question = generate_with_template("Tukar Unit Masa", "medium", "multiple_choice")

    assert not question["prompt_ms"].lower().startswith("tukar unit masa:")


def test_tukar_unit_masa_template_varies_prompt_and_answer_for_same_difficulty():
    questions = [generate_with_template("Tukar Unit Masa", "medium", "multiple_choice") for _ in range(6)]

    prompts = {question["prompt_ms"] for question in questions}
    answers = {question["expected_answer"] for question in questions}

    assert len(prompts) >= 4
    assert len(answers) >= 3
    assert all(not prompt.lower().startswith("tukar unit masa:") for prompt in prompts)


def test_medium_time_conversion_neighboring_templates_avoid_same_answer_collision():
    century_prompt, century_answer, *_ = build_time_conversion_question("medium", 142, 2, "Explanation.")
    extra_day_prompt, extra_day_answer, *_ = build_time_conversion_question("medium", 143, 2, "Explanation.")

    assert century_prompt != extra_day_prompt
    assert century_answer != extra_day_answer
