from app.services.hint_generator import generate_multilevel_hints


def test_generate_multilevel_hints_with_existing_hints(db, sample_question):
    """Test that generator skips if hints already exist"""
    sample_question.hint_level2_ms = "Existing level 2"
    sample_question.hint_level3_ms = "Existing level 3"
    db.commit()

    generate_multilevel_hints(sample_question, db)

    # Should not change existing hints
    assert sample_question.hint_level2_ms == "Existing level 2"
    assert sample_question.hint_level3_ms == "Existing level 3"


def test_generate_multilevel_hints_partial_exists_completes_missing_level3(db, sample_question, monkeypatch):
    """Test that generator keeps level2 and fills missing level3"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sample_question.hint_level2_ms = "Existing level 2"
    sample_question.hint_level3_ms = ""
    db.commit()

    generate_multilevel_hints(sample_question, db)

    assert sample_question.hint_level2_ms == "Existing level 2"
    assert sample_question.hint_level3_ms != ""


def test_generate_multilevel_hints_partial_exists_level3_completes_missing_level2(db, sample_question, monkeypatch):
    """Test that generator keeps level3 and fills missing level2"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sample_question.hint_level2_ms = ""
    sample_question.hint_level3_ms = "Existing level 3"
    db.commit()

    generate_multilevel_hints(sample_question, db)

    assert sample_question.hint_level3_ms == "Existing level 3"
    assert sample_question.hint_level2_ms != ""


def test_generate_multilevel_hints_fallback(db, sample_question, monkeypatch):
    """Test fallback to simple generation when API unavailable"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    sample_question.hint_level2_ms = ""
    sample_question.hint_level3_ms = ""
    db.commit()

    generate_multilevel_hints(sample_question, db)

    # Should have generated simple hints
    assert sample_question.hint_level2_ms != ""
    assert sample_question.hint_level3_ms != ""
    assert "langkah" in sample_question.hint_level2_ms.lower()
