import json
from datetime import datetime, timezone


def login_token(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def install_fake_ai_generator(monkeypatch):
    import app.main as main_module

    calls = []

    def fake_generate_question_ms(subtopic_title, difficulty, question_type="short_answer"):
        calls.append((subtopic_title, difficulty, question_type))
        prompt = f"Soalan AI ujian {len(calls)} untuk {subtopic_title}."
        expected_answer = str(100 + len(calls))
        options = []
        if question_type == "multiple_choice":
            options = [expected_answer, str(200 + len(calls)), str(300 + len(calls)), str(400 + len(calls))]
        return {
            "difficulty": difficulty,
            "question_type": question_type,
            "prompt_ms": prompt,
            "expected_answer": expected_answer,
            "options": options,
            "hint_ms": "Hint ujian tahap 1.",
            "explanation_ms": "Penjelasan ujian.",
            "source": "ai",
            "validation_status": "validated",
        }

    monkeypatch.setattr(main_module, "generate_question_ms", fake_generate_question_ms)
    return calls


def install_template_generator(monkeypatch):
    import app.main as main_module

    def fake_generate_question_ms(subtopic_title, difficulty, question_type="short_answer"):
        return {
            "difficulty": difficulty,
            "question_type": question_type,
            "prompt_ms": f"Soalan template untuk {subtopic_title}.",
            "expected_answer": "12",
            "options": [] if question_type == "short_answer" else ["12", "10", "8", "6"],
            "hint_ms": "Hint template tahap 1.",
            "explanation_ms": "Penjelasan template.",
            "source": "template",
            "validation_status": "validated",
        }

    monkeypatch.setattr(main_module, "generate_question_ms", fake_generate_question_ms)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_seeded_syllabus_has_eight_chapters(client):
    response = client.get("/syllabus")
    assert response.status_code == 200
    body = response.json()
    assert len(body["chapters"]) == 8
    assert body["chapters"][0]["title_ms"] == "Nombor Bulat dan Operasi"
    assert body["chapters"][1]["title_ms"] == "Pecahan, Perpuluhan dan Peratus"


def test_seeded_data_has_practical_classes_students_and_question_coverage(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    classes = client.get("/teacher/classes", headers=headers).json()["classes"]
    students = client.get("/teacher/students", headers=headers).json()["students"]

    questions = []
    page = 1
    while True:
        body = client.get(f"/teacher/questions?page={page}&page_size=100", headers=headers).json()
        questions.extend(body["questions"])
        if page >= body["pagination"]["total_pages"]:
            break
        page += 1

    chapter_two_questions = [question for question in questions if question["chapter_id"] == 2]
    assert len(classes) >= 2
    assert len(students) >= 5
    assert len(chapter_two_questions) >= 42
    assert any(question["question_type"] == "multiple_choice" for question in chapter_two_questions)
    multiple_choice = next(question for question in chapter_two_questions if question["question_type"] == "multiple_choice")
    assert len(multiple_choice["options"]) >= 3
    assert multiple_choice["expected_answer"] in multiple_choice["options"]


def test_teacher_questions_include_created_time_and_support_pagination_sorting(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/teacher/questions?page=1&page_size=5&sort_by=created_at&sort_dir=desc", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 5
    assert body["pagination"]["total"] >= 42
    assert len(body["questions"]) == 5
    assert body["questions"][0]["created_at"]
    created = [question["created_at"] for question in body["questions"]]
    assert created == sorted(created, reverse=True)


def test_teacher_login(client):
    response = client.post("/auth/login", json={"username": "cikgu", "password": "password123"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "teacher"
    assert body["access_token"]


def test_student_login(client):
    response = client.post("/auth/login", json={"username": "amin", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "student"


def test_student_can_get_next_question_and_submit_attempt(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    question_response = client.get("/student/next-question?subtopic_id=10", headers=headers)
    assert question_response.status_code == 200
    question = question_response.json()["question"]
    assert question["hint_ms"]
    assert question["hint_level2_ms"]
    assert question["hint_level3_ms"]
    attempt_response = client.post(
        "/student/attempts",
        headers=headers,
        json={"question_id": question["id"], "answer_text": question["expected_answer"], "time_seconds": 30},
    )
    assert attempt_response.status_code == 201
    assert attempt_response.json()["is_correct"] is True


def test_student_mistakes_include_answered_time_and_support_pagination_sorting(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    first_question = client.get("/student/next-question?subtopic_id=10", headers=headers).json()["question"]
    second_question = client.get("/student/next-question?subtopic_id=10", headers=headers).json()["question"]
    for question in [first_question, second_question]:
        client.post(
            "/student/attempts",
            headers=headers,
            json={"question_id": question["id"], "answer_text": "wrong", "time_seconds": 30},
        )

    response = client.get("/student/mistakes?page=1&page_size=1&sort_by=created_at&sort_dir=desc", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 1
    assert body["pagination"]["total"] >= 2
    assert len(body["mistakes"]) == 1
    assert body["mistakes"][0]["created_at"]


def test_student_next_question_rotates_after_attempt(client, monkeypatch):
    install_fake_ai_generator(monkeypatch)
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    first = client.get("/student/next-question?subtopic_id=10", headers=headers).json()["question"]
    client.post(
        "/student/attempts",
        headers=headers,
        json={"question_id": first["id"], "answer_text": first["expected_answer"], "time_seconds": 30},
    )
    second = client.get("/student/next-question?subtopic_id=10", headers=headers).json()["question"]
    assert second["id"] != first["id"]


def test_student_next_question_generates_fresh_question_before_bank_fallback(client, monkeypatch):
    install_fake_ai_generator(monkeypatch)
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    first = client.get("/student/next-question?subtopic_id=10", headers=headers).json()["question"]
    second = client.get("/student/next-question?subtopic_id=10", headers=headers).json()["question"]
    assert first["id"] != second["id"]
    assert first["source"] == "ai"
    assert second["source"] == "ai"


def test_student_next_question_uses_template_when_ai_and_bank_unavailable(client, monkeypatch):
    install_template_generator(monkeypatch)
    teacher_token = login_token(client, "cikgu")
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    chapter = client.post(
        "/teacher/chapters",
        headers=teacher_headers,
        json={"number": 99, "title_ms": "Topik Tanpa Bank"},
    ).json()
    subtopic = client.post(
        "/teacher/subtopics",
        headers=teacher_headers,
        json={"chapter_id": chapter["id"], "title_ms": "Subtopik Tanpa Bank", "activity_type": "practice"},
    ).json()

    student_token = login_token(client, "amin")
    response = client.get(
        f"/student/next-question?subtopic_id={subtopic['id']}",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    question = response.json()["question"]
    assert question["source"] == "template"
    assert question["subtopic_id"] == subtopic["id"]
    assert question["hint_ms"]
    assert question["hint_level2_ms"]
    assert question["hint_level3_ms"]


def test_student_next_question_fills_missing_bank_hint_levels(client, monkeypatch):
    install_template_generator(monkeypatch)
    teacher_token = login_token(client, "cikgu")
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    chapter = client.post(
        "/teacher/chapters",
        headers=teacher_headers,
        json={"number": 100, "title_ms": "Topik Hint Bank"},
    ).json()
    subtopic = client.post(
        "/teacher/subtopics",
        headers=teacher_headers,
        json={"chapter_id": chapter["id"], "title_ms": "Subtopik Hint Bank", "activity_type": "practice"},
    ).json()
    created = client.post(
        "/teacher/questions",
        headers=teacher_headers,
        json={
            "chapter_id": chapter["id"],
            "subtopic_id": subtopic["id"],
            "difficulty": "medium",
            "question_type": "short_answer",
            "prompt_ms": "Soalan bank hanya ada hint pertama.",
            "expected_answer": "8",
            "options": [],
            "hint_ms": "Hint bank tahap 1.",
            "explanation_ms": "Penjelasan bank.",
        },
    ).json()["question"]
    assert created["hint_level2_ms"] == ""
    assert created["hint_level3_ms"] == ""

    student_token = login_token(client, "amin")
    response = client.get(
        f"/student/next-question?subtopic_id={subtopic['id']}",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    question = response.json()["question"]
    assert question["id"] == created["id"]
    assert question["hint_ms"] == "Hint bank tahap 1."
    assert question["hint_level2_ms"]
    assert question["hint_level3_ms"]


def test_diagnostic_session_starts_across_core_topics(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/student/diagnostic/start", headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["total_questions"] >= 8
    assert len(body["chapters"]) >= 4


def test_comprehensive_practice_starts_after_completed_diagnostic_without_weak_mastery(client):
    from app.models import DiagnosticSession

    teacher_token = login_token(client, "cikgu")
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    class_id = client.get("/teacher/classes", headers=teacher_headers).json()["classes"][0]["id"]
    student = client.post(
        "/teacher/students",
        headers=teacher_headers,
        json={
            "username": "compready",
            "password": "password123",
            "full_name": "Comprehensive Ready",
            "parent_email": "compready@example.com",
            "class_id": class_id,
        },
    ).json()

    with client.app.state.session_factory() as session:
        session.add(
            DiagnosticSession(
                student_id=student["id"],
                status="completed",
                current_question_number=8,
                total_questions=8,
                state_json=json.dumps({"results": []}, ensure_ascii=False),
                completed_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    student_token = login_token(client, "compready")
    response = client.post(
        "/student/comprehensive-practice/start",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["total_questions"] == 15
    assert body["weak_subtopics"] == []


def test_student_progress_returns_mastery_summary(client):
    token = login_token(client, "amin")
    response = client.get("/student/progress", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "chapters" in response.json()


def test_teacher_can_create_update_and_deactivate_class(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/teacher/classes",
        headers=headers,
        json={"name": "Tahun 5 Amanah", "year_level": 5, "section": "A"},
    )
    assert create_response.status_code == 201
    class_id = create_response.json()["id"]
    update_response = client.put(
        f"/teacher/classes/{class_id}",
        headers=headers,
        json={"name": "Tahun 5 Amanah Updated", "year_level": 5, "section": "A"},
    )
    assert update_response.status_code == 200
    delete_response = client.delete(f"/teacher/classes/{class_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False


def test_teacher_can_create_update_and_deactivate_student(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    classes = client.get("/teacher/classes", headers=headers).json()["classes"]
    class_id = classes[0]["id"]
    create_response = client.post(
        "/teacher/students",
        headers=headers,
        json={
            "username": "nora",
            "password": "password123",
            "full_name": "Nora Aina",
            "parent_email": "nora.parent@example.com",
            "class_id": class_id,
        },
    )
    assert create_response.status_code == 201
    student_id = create_response.json()["id"]
    update_response = client.put(
        f"/teacher/students/{student_id}",
        headers=headers,
        json={
            "username": "nora",
            "password": "password123",
            "full_name": "Nora Aina Updated",
            "parent_email": "nora.parent@example.com",
            "class_id": class_id,
        },
    )
    assert update_response.status_code == 200
    delete_response = client.delete(f"/teacher/students/{student_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False


def test_teacher_create_student_rejects_unknown_class_id(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/teacher/students",
        headers=headers,
        json={
            "username": "ghostclass",
            "password": "password123",
            "full_name": "Ghost Class Student",
            "parent_email": "ghost@example.com",
            "class_id": 9999,
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Kelas tidak ditemui."


def test_teacher_can_create_update_and_deactivate_syllabus_items(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    chapter_response = client.post(
        "/teacher/chapters",
        headers=headers,
        json={"number": 9, "title_ms": "Latihan Tambahan"},
    )
    assert chapter_response.status_code == 201
    chapter_id = chapter_response.json()["id"]
    subtopic_response = client.post(
        "/teacher/subtopics",
        headers=headers,
        json={"chapter_id": chapter_id, "title_ms": "Latihan Campuran", "activity_type": "practice"},
    )
    assert subtopic_response.status_code == 201
    subtopic_id = subtopic_response.json()["id"]
    update_response = client.put(
        f"/teacher/subtopics/{subtopic_id}",
        headers=headers,
        json={"chapter_id": chapter_id, "title_ms": "Latihan Campuran Updated", "activity_type": "practice"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title_ms"] == "Latihan Campuran Updated"
    delete_response = client.delete(f"/teacher/chapters/{chapter_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False


def test_teacher_question_crud_preserves_three_hint_levels(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "chapter_id": 2,
        "subtopic_id": 10,
        "difficulty": "medium",
        "question_type": "short_answer",
        "prompt_ms": "Soalan manual dengan tiga petunjuk.",
        "expected_answer": "42",
        "options": [],
        "hint_ms": "Hint 1 manual.",
        "hint_level2_ms": "Hint 2 manual.",
        "hint_level3_ms": "Hint 3 manual.",
        "explanation_ms": "Penjelasan manual.",
    }

    create_response = client.post("/teacher/questions", headers=headers, json=payload)
    assert create_response.status_code == 201
    question = create_response.json()["question"]
    assert question["hint_ms"] == "Hint 1 manual."
    assert question["hint_level2_ms"] == "Hint 2 manual."
    assert question["hint_level3_ms"] == "Hint 3 manual."

    list_response = client.get("/teacher/questions?page=1&page_size=100", headers=headers)
    listed = next(item for item in list_response.json()["questions"] if item["id"] == question["id"])
    assert listed["hint_level2_ms"] == "Hint 2 manual."
    assert listed["hint_level3_ms"] == "Hint 3 manual."

    updated_payload = {
        **payload,
        "hint_ms": "Hint 1 dikemas kini.",
        "hint_level2_ms": "Hint 2 dikemas kini.",
        "hint_level3_ms": "Hint 3 dikemas kini.",
    }
    update_response = client.put(f"/teacher/questions/{question['id']}", headers=headers, json=updated_payload)
    assert update_response.status_code == 200
    updated = update_response.json()["question"]
    assert updated["hint_ms"] == "Hint 1 dikemas kini."
    assert updated["hint_level2_ms"] == "Hint 2 dikemas kini."
    assert updated["hint_level3_ms"] == "Hint 3 dikemas kini."


def test_teacher_can_generate_question(client, monkeypatch):
    install_fake_ai_generator(monkeypatch)
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/teacher/questions/generate",
        headers=headers,
        json={"chapter_id": 2, "subtopic_id": 10, "difficulty": "medium"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["question"]["source"] == "ai"
    assert body["question"]["validation_status"] == "validated"


def test_teacher_generate_uses_template_fallback_when_ai_unavailable(client, monkeypatch):
    install_template_generator(monkeypatch)
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/teacher/questions/generate",
        headers=headers,
        json={"chapter_id": 2, "subtopic_id": 10, "difficulty": "medium"},
    )
    assert response.status_code == 201
    question = response.json()["question"]
    assert question["source"] == "template"
    assert question["hint_ms"]
    assert question["hint_level2_ms"]
    assert question["hint_level3_ms"]


def test_teacher_can_generate_multiple_choice_question(client, monkeypatch):
    install_fake_ai_generator(monkeypatch)
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/teacher/questions/generate",
        headers=headers,
        json={"chapter_id": 2, "subtopic_id": 10, "difficulty": "medium", "question_type": "multiple_choice"},
    )
    assert response.status_code == 201
    question = response.json()["question"]
    assert question["question_type"] == "multiple_choice"
    assert len(question["options"]) >= 3
    assert question["expected_answer"] in question["options"]


def test_teacher_can_generate_multiple_distinct_questions(client, monkeypatch):
    install_fake_ai_generator(monkeypatch)
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post(
        "/teacher/questions/generate",
        headers=headers,
        json={"chapter_id": 2, "subtopic_id": 10, "difficulty": "medium"},
    ).json()["question"]
    second = client.post(
        "/teacher/questions/generate",
        headers=headers,
        json={"chapter_id": 2, "subtopic_id": 10, "difficulty": "medium"},
    ).json()["question"]
    assert second["id"] != first["id"]
    assert second["prompt_ms"] != first["prompt_ms"]


def test_teacher_generate_retries_when_generated_question_already_exists(client, monkeypatch):
    import app.main as main_module

    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    existing = client.post(
        "/teacher/questions",
        headers=headers,
        json={
            "chapter_id": 2,
            "subtopic_id": 10,
            "difficulty": "medium",
            "question_type": "multiple_choice",
            "prompt_ms": "Soalan pendua untuk ujian.",
            "expected_answer": "100",
            "options": ["100", "101", "102", "103"],
            "hint_ms": "Duplicate hint.",
            "explanation_ms": "Duplicate explanation.",
        },
    ).json()["question"]
    calls = []

    def fake_generate_question_ms(subtopic_title, difficulty, question_type="short_answer"):
        calls.append(subtopic_title)
        if len(calls) <= 9:
            return {
                "difficulty": difficulty,
                "question_type": question_type,
                "prompt_ms": existing["prompt_ms"],
                "expected_answer": existing["expected_answer"],
                "options": existing["options"],
                "hint_ms": "Duplicate hint.",
                "explanation_ms": "Duplicate explanation.",
                "source": "ai",
                "validation_status": "validated",
            }
        return {
            "difficulty": difficulty,
            "question_type": question_type,
            "prompt_ms": "Soalan unik selepas semakan pendua.",
            "expected_answer": "999",
            "options": ["999", "998", "997", "996"],
            "hint_ms": "Unique hint.",
            "explanation_ms": "Unique explanation.",
            "source": "ai",
            "validation_status": "validated",
        }

    monkeypatch.setattr(main_module, "generate_question_ms", fake_generate_question_ms)
    response = client.post(
        "/teacher/questions/generate",
        headers=headers,
        json={"chapter_id": 2, "subtopic_id": 10, "difficulty": "medium", "question_type": "multiple_choice"},
    )
    assert response.status_code == 201
    question = response.json()["question"]
    assert len(calls) == 10
    assert question["prompt_ms"] == "Soalan unik selepas semakan pendua."


def test_teacher_dashboard_returns_class_analytics(client):
    token = login_token(client, "cikgu")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/teacher/analytics/classes/1", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert "students" in body
    assert "weak_subtopics" in body
