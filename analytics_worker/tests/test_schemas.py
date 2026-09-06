import pytest
from pydantic import ValidationError

from analytics_worker.schemas import StockQuery

def test_valid_query():
    """Тестирование модели входных параметров, когда заполнены оба параметра."""

    query = StockQuery(warehouse="WH-A", sku="SKU-1")

    assert query.warehouse == "WH-A"
    assert query.sku == "SKU-1"


def test_valid_query_no_sku():
    """Тестирование модели входных параметров, когда не заполнена единица товара."""

    query = StockQuery(warehouse="WH-A")

    assert query.warehouse == "WH-A"
    assert query.sku is None


def test_query_strips_sku():
    """Тестирование модели входных параметров, когда у единицы товара есть лишние пробелы."""

    query = StockQuery(warehouse=" WH-A ", sku=" SKU-1 ")

    assert query.warehouse == "WH-A"
    assert query.sku == "SKU-1"


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"sku": "SKU-1"}, "warehouse"),
        ({"warehouse": "", "sku": "SKU-1"}, "warehouse"),
        ({"warehouse": "   ", "sku": "SKU-1"}, "warehouse"),
        ({"warehouse": "\t"}, "warehouse"),
        ({"warehouse": "WH-A", "sku": "  "}, "sku"),
    ],
)
def test_invalid_query(payload, field):
    """Тестирование модели входных параметров на обязательность заполнения."""
    
    with pytest.raises(ValidationError) as e:
        StockQuery(**payload)

    assert field in e.value.errors()[0]["loc"]