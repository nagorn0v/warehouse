import pytest
from pydantic import ValidationError

from inventory_api.schemas import IssueIn, ReceiptIn


def test_valid_receipt():
    """Тестирует успешную валидацию корректного ReceiptIn."""

    receipt = ReceiptIn(sku="SKU-1", qty=5, warehouse="WH-A")
    assert receipt.sku == "SKU-1"
    assert receipt.qty == 5
    assert receipt.warehouse == "WH-A"


def test_valid_issue():
    """Тестирует успешную валидацию корректного IssueIn."""

    issue = IssueIn(sku="SKU-1", qty=5, warehouse="WH-A")
    assert issue.sku == "SKU-1"
    assert issue.qty == 5
    assert issue.warehouse == "WH-A"


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"qty": 5, "warehouse": "WH-A"}, "sku"),
        ({"sku": "", "qty": 5, "warehouse": "WH-A"}, "sku"),
        ({"sku": "   ", "qty": 5, "warehouse": "WH-A"}, "sku"),
        ({"sku": "SKU-1", "warehouse": "WH-A"}, "qty"),
        ({"sku": "SKU-1", "qty": 0, "warehouse": "WH-A"}, "qty"),
        ({"sku": "SKU-1", "qty": -1, "warehouse": "WH-A"}, "qty"),
        ({"sku": "SKU-1", "qty": 5}, "warehouse"),
        ({"sku": "SKU-1", "qty": 5, "warehouse": ""}, "warehouse"),
        ({"sku": "SKU-1", "qty": 5, "warehouse": "  "}, "warehouse"),
        ({"sku": "SKU-1", "qty": 5, "warehouse": "\t"}, "warehouse"),
        ({}, "sku"),
    ],
)
def test_invalid_receipt(payload, field):
    """Тестирует ошибку валидации ReceiptIn при невалидном/отсутствующем поле."""

    with pytest.raises(ValidationError) as e:
        ReceiptIn(**payload)

    assert field in e.value.errors()[0]["loc"]


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"qty": 5, "warehouse": "WH-A"}, "sku"),
        ({"sku": "", "qty": 5, "warehouse": "WH-A"}, "sku"),
        ({"sku": "   ", "qty": 5, "warehouse": "WH-A"}, "sku"),
        ({"sku": "SKU-1", "qty": 0, "warehouse": "WH-A"}, "qty"),
        ({"sku": "SKU-1", "qty": 5, "warehouse": " "}, "warehouse"),
        ({}, "sku"),
    ],
)
def test_invalid_issue(payload, field):
    """Тестирует ошибку валидации IssueIn при невалидном поле."""

    with pytest.raises(ValidationError) as e:
        IssueIn(**payload)
        
    assert field in e.value.errors()[0]["loc"]