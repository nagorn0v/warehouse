from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.functional_validators import BeforeValidator


def str_to_bool(value: bool | str) -> bool:
    """Приводит "bool-значение" к bool и возвращает его.
       Допускается только строка в виде true/false или bool.

    Args:
        value: исходное значение

    Raises:
        ValueError: если значение не является признаваемым bool
    """

    result = None
    if isinstance(value, bool):
        result = value
    else:    
        lowered_val = str(value).strip().lower()
        if lowered_val == "true":
            result = True
        if lowered_val == "false":
            result = False

    if result is None:
        raise ValueError("must be 'true' or 'false'")
    else:
        return result


class StockOpIn(BaseModel):
    """Входные данные операции со складом (приход/расход).

    Attributes:
        sku: идентификатор товара
        qty: количество
        warehouse: идентификатор склада
    """

    sku: str = Field(min_length=1)
    qty: int = Field(gt=0)
    warehouse: str = Field(min_length=1)

    @field_validator("sku", "warehouse")
    @classmethod
    def strip_required(cls, value: str) -> str:
        """Убирает пробелы со строки.

        Args:
            value: значение поля.

        Returns:
            Очищенное значение.

        Raises:
            ValueError: если после обрезки строка пуста.
        """

        value = value.strip()
        if not value:

            raise ValueError("must not be blank")
        
        return value


class ReceiptIn(StockOpIn):
    """Входные данные прихода."""

    pass


class IssueIn(StockOpIn):
    """Входные данные расхода."""

    pass


class StockOpOut(BaseModel):
    """Выходные данные созданной операции со складом.

    Attributes:
        id: идентификатор строки stock_events.
        sku: идентификатор товара.
        qty: количество.
        warehouse: идентификатор склада.
        created_at: время создания события.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    qty: int
    warehouse: str
    created_at: datetime


class IssueOut(StockOpOut):
    """Выходные данные созданного расхода."""

    pass


class StockQuery(BaseModel):
    """Параметры запроса остатков по складу/товару.

    Attributes:
        warehouse: идентификатор склада.
        sku: идентификатор товара.
    """

    warehouse: str = Field(min_length=1)
    sku: str | None = None

    @field_validator("warehouse")
    @classmethod
    def strip_required(cls, value: str) -> str:
        """Обрезает пробелы и отклоняет пустую строку.

        Args:
            value: значение поля.

        Returns:
            Очищенное значение.

        Raises:
            ValueError: если после обрезки строка пуста.
        """

        value = value.strip()
        if not value:

            raise ValueError("value is required")
        
        return value

    @field_validator("sku")
    @classmethod
    def strip_optional(cls, value):
        """Обрезает пробелы у опциональной строки.

        Args:
            value: значение поля.

        Returns:
            Очищенное значение или None (в т.ч. если строка пустая).
        """

        if value is None:

            return value
        
        value = value.strip()
        if not value:

            return None
        
        return value


class StockSnapshot(BaseModel):
    """Остаток товара на складе.

    Attributes:
        warehouse: идентификатор склада.
        sku: идентификатор товара.
        qty: остаток.
    """

    warehouse: str
    sku: str
    qty: int


class StockLine(BaseModel):
    """Строка остатка по товару.

    Attributes:
        sku: идентификатор товара.
        qty: остаток.
    """

    sku: str
    qty: int


class StockList(BaseModel):
    """Остатки по всем товарам склада.

    Attributes:
        warehouse: идентификатор склада.
        skus: список строк остатков.
    """

    warehouse: str
    skus: list[StockLine]


class StockSummaryQuery(BaseModel):
    """Параметры запроса сводки по складам.

    Attributes:
        top_n: количество товаров в топе.
        show_wh: признак расшифровки по складам.
    """

    top_n: int | None = None
    show_wh: Annotated[bool | None, BeforeValidator(str_to_bool)] = None

    @field_validator("top_n")
    @classmethod
    def check_top_n(cls, value):
        """Проверяет, что top_n не меньше 1.

        Args:
            value: значение top_n.

        Returns:
            Проверенное значение (или None).

        Raises:
            ValueError: если значение меньше 1.
        """

        if value is not None and value < 1:

            raise ValueError("value must be >= 1")
        
        return value


class WarehouseSummary(BaseModel):
    """Сводка по одному складу.

    Attributes:
        warehouse: идентификатор склада.
        total_qty: суммарный остаток.
        sku_count: количество уникальных товаров.
    """

    warehouse: str
    total_qty: int
    sku_count: int


class WarehouseQty(BaseModel):
    """Количество по складу в сводке товара.

    Attributes:
        warehouse: идентификатор склада.
        qty: остаток.
    """

    warehouse: str
    qty: int


class TopSku(BaseModel):
    """Товар в топе сводки.

    Attributes:
        sku: идентификатор товара.
        total_qty: суммарный остаток.
        warehouses: расшифровка по складам (опционально).
    """

    sku: str
    total_qty: int
    warehouses: list[WarehouseQty] | None = None


class StockSummary(BaseModel):
    """Сводка по складам и топу товаров.

    Attributes:
        warehouses: сводка по каждому складу.
        top_skus: топ товаров.
    """

    warehouses: list[WarehouseSummary]
    top_skus: list[TopSku]