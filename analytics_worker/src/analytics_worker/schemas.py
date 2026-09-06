from pydantic import BaseModel, Field, field_validator


class StockQuery(BaseModel):
    """Модель входных данных запроса остатков."""

    warehouse: str = Field(min_length=1)
    sku: str | None = None

    @field_validator("warehouse", "sku")
    @classmethod
    def strip_optional(cls, value):
        """Убирает пробелы по краям.
        
        Args:
            value: обрабатываемое значение.
        """

        if value is None:
            return value
        
        value = value.strip()
        if not value:

            raise ValueError("value is required")
        
        return value


class StockSnapshot(BaseModel):
    """Модель выходных данных в разрезе склада и единицы товара."""

    warehouse: str
    sku: str
    qty: int


class StockLine(BaseModel):
    """Модель выходных данных в разрезе единицы товара."""

    sku: str
    qty: int


class StockList(BaseModel):
    """Модель выходных данных в разрезе склада и всех единиц товара."""
    
    warehouse: str
    skus: list[StockLine]