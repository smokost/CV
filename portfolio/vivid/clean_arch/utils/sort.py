from functools import cmp_to_key
from operator import attrgetter, itemgetter
from typing import Any, Callable


def multikeysort(items: list[Any], columns: str, attrs: bool = True) -> list[Any]:
    """Perform a multiple column sort on a list of dictionaries or objects.

    :param items: List of dictionaries or objects to be sorted.
    :param columns: Comma separated columns to sort by, optionally preceded by a '-' for descending order.
    :param attrs: True if items are objects, False if items are dictionaries.

    :return: Sorted list of items.

    >>> from collections import namedtuple
    >>> Customer = namedtuple('Customer', ['id', 'opens', 'clicks'])
    >>> customer1 = Customer(id=1, opens='4', clicks='8')
    >>> customer2 = Customer(id=2, opens='4', clicks='7')
    >>> customer3 = Customer(id=3, opens='5', clicks='1')
    >>> customers = [customer1, customer2, customer3]
    >>> assert multikeysort(customers, '-opens,clicks') == [customer3, customer2, customer1]
    >>> assert multikeysort(customers, 'opens,-clicks') == [customer1, customer2, customer3]
    >>> assert multikeysort(customers, 'opens,clicks') == [customer2, customer1, customer3]
    >>> assert multikeysort(customers, '-opens,-clicks') == [customer3, customer1, customer2]
    """
    getter = attrgetter if attrs else itemgetter

    def get_comparers() -> list[tuple[Callable[[Any], Any], int]]:
        comparers: list[tuple[Callable[[Any], Any], int]] = []

        for col in columns.split(','):
            col = col.strip()
            if col.startswith('-'):  # If descending, strip '-' and create a comparer with reverse order
                key = getter(col[1:])
                order = -1
            else:  # If ascending, use the column directly
                key = getter(col)
                order = 1

            comparers.append((key, order))
        return comparers

    def custom_compare(left: Any, right: Any) -> int:
        """Custom comparison function to handle multiple keys"""
        for fn, reverse in get_comparers():
            result = (fn(left) > fn(right)) - (fn(left) < fn(right))
            if result != 0:
                return result * reverse
        return 0

    return sorted(items, key=cmp_to_key(custom_compare))
