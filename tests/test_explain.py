import pytest

from cronlens.explain import describe
from cronlens.expr import parse


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("* * * * *", "Every minute"),
        ("*/15 * * * *", "Every 15 minutes"),
        ("5 * * * *", "At minute 5 past every hour"),
        ("5,35 * * * *", "At minutes 5 and 35 past every hour"),
        ("0 9 * * *", "At 09:00"),
        ("30 9,17 * * *", "At 09:30 and 17:30"),
        ("0 9 * * 1-5", "At 09:00 on Monday through Friday"),
        ("0 0 1 * *", "At 00:00 on the 1st of the month"),
        ("0 0 1,15 * *", "At 00:00 on the 1st and 15th of the month"),
        ("0 0 13 * 5", "At 00:00 on the 13th of the month or on Friday"),
        (
            "0 0 */10 * 1",
            "At 00:00 on the 1st, 11th, 21st and 31st of the month if it is also Monday",
        ),
        ("0 6 * 1-3 *", "At 06:00 in January through March"),
        ("0 */2 * * *", "At minute 0 past every 2 hours"),
        ("* 3 * * *", "Every minute from 03:00 to 03:59"),
        ("* 3-4 * * *", "Every minute during hours 3 and 4"),
        ("0 0 29 2 *", "At 00:00 on the 29th of the month in February"),
        (
            "15 0-23/3,1 * * *",
            "At minute 15 past hours 0, 1, 3, 6, 9, 12, 15, 18 and 21",
        ),
        ("10,40 8-17 * * *", "At minutes 10 and 40 past hours 8 through 17"),
        ("@weekly", "At 00:00 on Sunday"),
        ("0 12 * * 0,6", "At 12:00 on Sunday and Saturday"),
        ("0 12 22 * *", "At 12:00 on the 22nd of the month"),
        ("0 12 11,12,13 * *", "At 12:00 on the 11th through 13th of the month"),
    ],
)
def test_describe(expression: str, expected: str) -> None:
    assert describe(parse(expression)) == expected
