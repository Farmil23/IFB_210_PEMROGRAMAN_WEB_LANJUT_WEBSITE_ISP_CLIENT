from datetime import datetime

from zoneinfo import ZoneInfo

WIB = ZoneInfo('Asia/Jakarta')

WIB_LABEL = 'WIB'


def now_wib():

    return datetime.now(WIB).replace(tzinfo=None)


def ensure_wib(dt):

    if dt is None:

        return None

    if dt.tzinfo is None:

        return dt

    return dt.astimezone(WIB).replace(tzinfo=None)


def format_wib(dt, fmt='%d %b %Y, %H:%M'):

    if dt is None:

        return '—'

    return ensure_wib(dt).strftime(fmt)
