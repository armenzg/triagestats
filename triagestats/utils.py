# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import dateutil.parser
import pytz


MONTHS = ['Jan', 'Feb', 'Mar',
          'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep',
          'Oct', 'Nov', 'Dec']


def get_num_months(d1, d2):
    """Get the number of months between two dates (included)
    """
    if d1 > d2:
        d1, d2 = d2, d1

    if d1.year == d2.year:
        return d2.month - d1.month + 1

    m1 = 13 - d1.month
    m2 = d2.month
    m = ((d2.year - 1) - (d1.year + 1) + 1) * 12

    return m1 + m2 + m


def get_months_index(d1, d):
    return get_num_months(d1, d) - 1


def get_months_labels(d1, d2):
    if d1 > d2:
        d1, d2 = d2, d1

    months = []
    fmt = '{}-{}'
    while d1 <= d2:
        months.append(fmt.format(d1.year, MONTHS[d1.month - 1]))
        d1 += relativedelta(months=1)

    return months


def get_date(dt):
    """Get a datetime from a string 'Year-month-day'

    Args:
        dt (str): a date

    Returns:
        datetime: a datetime object
    """
    assert dt

    if isinstance(dt, datetime):
        return as_utc(dt)

    if dt == 'today':
        return pytz.utc.localize(datetime.utcnow())
    elif dt == 'tomorrow':
        return pytz.utc.localize(datetime.utcnow() + relativedelta(days=1))
    elif dt == 'yesterday':
        return pytz.utc.localize(datetime.utcnow() - relativedelta(days=1))

    return as_utc(dateutil.parser.parse(dt))


def as_utc(d):
    """Convert a date in UTC

    Args:
        d (datetime.datetime): the date

    Returns:
        datetime.datetime: the localized date
    """
    if isinstance(d, datetime):
        if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
            return pytz.utc.localize(d)
        return d.astimezone(pytz.utc)
    elif isinstance(d, date):
        return pytz.utc.localize(datetime(d.year, d.month, d.day))
