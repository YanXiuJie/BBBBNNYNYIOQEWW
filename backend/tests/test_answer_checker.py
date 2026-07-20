from app.services.answer_checker import is_equivalent_answer


def test_fraction_equivalence():
    assert is_equivalent_answer("1/2", "2/4")


def test_decimal_fraction_equivalence():
    assert is_equivalent_answer("0.5", "1/2")


def test_percentage_decimal_equivalence():
    assert is_equivalent_answer("50%", "0.5")


def test_money_answer_equivalence():
    assert is_equivalent_answer("36", "RM36")
    assert is_equivalent_answer("RM36.00", "36")


def test_wrong_answer_returns_false():
    assert not is_equivalent_answer("4/10", "11/12")
