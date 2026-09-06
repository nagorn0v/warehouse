from enum import Enum


class StockOperation(str, Enum):
    """Типы операций склада.

    Attributes:
        receipt: приход товара.
        issue: расход товара.
    """

    receipt = "receipt"
    issue = "issue"


class StockStream(str, Enum):
    """Имена стримов Redis для публикации событий.

    Attributes:
        receipt: приход товара.
        issue: расход товара.
    """

    receipt = "inventory.receipt"
    issue = "inventory.issue"