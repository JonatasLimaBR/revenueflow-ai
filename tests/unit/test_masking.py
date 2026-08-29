from revenueflow.observability import mask


def test_masks_phone_numbers() -> None:
    assert "5511999999999" not in mask("ligue para +55 11 99999-9999 hoje")
    assert mask("+5511999999999") == "***"


def test_masks_email() -> None:
    assert mask("contato joao@example.com aqui") == "contato *** aqui"


def test_masks_nested_structures() -> None:
    payload = {
        "phone": "+5511988887777",
        "notes": ["chamar no +55 11 98888-7777", "sem email"],
        "count": 3,
    }
    masked = mask(payload)
    assert masked["phone"] == "***"
    assert "98888" not in masked["notes"][0]
    assert masked["count"] == 3


def test_masks_extra_terms_case_insensitively() -> None:
    assert mask("cliente Maria Silva", extra_terms=["maria silva"]) == "cliente ***"


def test_non_string_scalars_pass_through() -> None:
    assert mask(42) == 42
    assert mask(None) is None
    assert mask(True) is True
