import datetime
import hashlib
import requests
import time
from requests_oauth2 import OAuth2

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.cache import cache
from django.db import connections
import json

PENALTY_TIME = 12 * 60 * 60
PENALTY_MULT = 0.2

KEY_ERRORS = {
    '202',  # API key authentication failure.
    '203',  # Authentication failure.
    '204',  # Authentication failure.
    '205',  # Authentication failure (final pass).
    '207',  # Not available for NPC corporations.
    '210',  # Authentication failure.
    '211',  # Login denied by account status.
    '212',  # Authentication failure (final pass).
    '220',  # Invalid Corporation Key. Key owner does not fullfill role requirements anymore.
    '222',  # Key has expired. Contact key owner for access renewal.
    '223',  # Authentication failure. Legacy API keys can no longer be used. Please create a new key on support.eveonline.com and make sure your application supports Customizable API Keys.
}


def dictfetchall(query, cache_key=None, cache_time=None):
    "Returns all rows from a cursor as a dict"
    from django.core.cache import caches
    query_cache = caches['default']
    if cache_time is not None:
        results = query_cache.get(cache_key)
        if results is not None:
            return results

    cursor = connections['default'].cursor()
    cursor.execute(query)
    desc = cursor.description
    results = [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
    ]

    cursor.close()

    if cache_time is not None:
        query_cache.set(cache_key, results, cache_time)

    return results

def total_seconds(delta):
    """Convert a datetime.timedelta object into a number of seconds"""
    return (delta.days * 24 * 60 * 60) + delta.seconds


def set_cookie(response, key, value, days_expire=7):
    if days_expire is None:
        max_age = 365 * 24 * 60 * 60  #one year
    else:
        max_age = days_expire * 24 * 60 * 60
    expires = datetime.datetime.strftime(datetime.datetime.utcnow() + datetime.timedelta(seconds=max_age), "%a, %d-%b-%Y %H:%M:%S GMT")
    response.set_cookie(key, value, max_age=max_age, expires=expires, domain=settings.SESSION_COOKIE_DOMAIN, secure=settings.SESSION_COOKIE_SECURE or None)


class ApiHelper:
    # Logger instance

    # Requests session so we get HTTP Keep-Alive
    _session = requests.Session()
    _session.headers.update({
        'User-Agent': 'PGSUS-tasks',
        'Accept-Encoding': 'gzip, deflate',
    })
    # Limit each session to a single connection
    _session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1))
    _session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1))

    _taskstate = None

    # -----------------------------------------------------------------------

    def __init__(self):
        """
        Tasks should call this in their run() method to initialise stuff.
        Returns False if anything bad happens.
        """

        self._started = time.time()
        self._api_log = []
        self._cache_delta = None

        self._taskstate = None
        self.root = None

    # -----------------------------------------------------------------------

    def fetch_url(self, url, params):
        """
        Fetch a URL directly without any API magic.
        """
        start = time.time()
        try:
            if params:
                r = self._session.post(url, params)
            else:
                r = self._session.get(url)
            data = r.text
        except Exception:
            # self._increment_backoff(e)
            return False

        self._api_log.append((url, time.time() - start))

        # If the status code is bad return False
        if not r.status_code == requests.codes.ok:
            # self._increment_backoff('Bad status code: %s' % (r.status_code))
            return False

        return data

    def fetch_esi_url(self, url, access_token, headers_to_return=None, method='post'):
        """
        Fetch an ESI URL
        """

        cache_key = self._get_cache_key(url, {})
        cached_data = cache.get(cache_key)

        retry = 3

        data = None

        headers = dict()

        if cached_data is None:
            sleep_for = self._get_backoff()
            if sleep_for > 0:
                time.sleep(sleep_for)

            start = time.time()
            while retry > 0:
                try:
                    if '?' not in url:
                        url += '?'

                    r = self._session.request(method, url + '&token=' + access_token,
                                           headers={'Authorization': 'Bearer %s' % access_token})

                    data = r.text
                    if 'date' in r.headers and 'expires' in r.headers:
                        current = self.parse_esi_date(r.headers['date'])
                        until = self.parse_esi_date(r.headers['expires'])

                        self._cache_delta = until - current
                    if headers_to_return is not None:
                        for header in headers_to_return:
                            headers[header] = r.headers[header] if header in r.headers else None
                    break
                except Exception, e:
                    # self._increment_backoff(e)
                    retry -= 1
                    print("Exception! %s" % repr(e))
                    return False

            if not r.status_code == requests.codes.ok:
                if r.status_code == '400' or r.status_code == 400:
                    self._cache_delta = datetime.timedelta(hours=4)
                    self.log_warn('400 error, caching for 2 hours')
                    print("400!")
                return False
        else:
            data = cached_data

        if data:
            try:
                self.json = json.loads(data)
            except Exception:
                print("Cannot Parse! %s" % data)
                return False

            if cached_data is None and self._cache_delta is not None:
                cache_expires = total_seconds(self._cache_delta) + 10

                if cache_expires >= 0:
                    cache.set(cache_key, data, cache_expires)

        if headers_to_return is not None:
            return data, headers
        return data

    # -----------------------------------------------------------------------

    def parse_xml(self, data):
        """
        Parse XML and return an ElementTree.
        """
        return ET.fromstring(data.encode('utf-8'))

    def get_access_token(self, refresh_token):
        oauth_handler = self.oauth_handler()

        response = oauth_handler.get_token("", grant_type='refresh_token', refresh_token=refresh_token)
        if response is not None and 'access_token' in response:
            return response['access_token'], datetime.datetime.now() + datetime.timedelta(
                seconds=response['expires_in'])

        return None

    def oauth_handler(self):
        return OAuth2(
            settings.OAUTH_CLIENT_ID,
            settings.OAUTH_CLIENT_SECRET,
            settings.OAUTH_SERVER_URL,
            settings.OAUTH_CALLBACK_URL
        )

    # -----------------------------------------------------------------------

    def _get_cache_key(self, url, params):
        """
        Get an MD5 hash of data to use as a cache key.
        """
        key_data = '%s:%s' % (url, repr(sorted(params.items())))
        h = hashlib.new('md5')
        h.update(key_data)
        return h.hexdigest()

    # -----------------------------------------------------------------------

    def _get_backoff(self):
        """
        Get a time in seconds for the current backoff value. Initialises cache
        keys to 0 if they have mysteriously disappeared.
        """
        backoff_count = cache.get('backoff_count')
        # Initialise the cache value if it's missing
        if backoff_count is None:
            cache.set('backoff_count', 0)
            cache.set('backoff_last', 0)
            return 0

        if backoff_count == 0:
            return 0

        # Calculate the sleep value and return it
        return 0.5 * (2 ** min(6, backoff_count - 1))
        # return sleep_for

    def _increment_backoff(self, e):
        """
        Helper function to increment the backoff counter
        """
        # Initialise the cache value if it's missing
        if cache.get('backoff_count') is None:
            cache.set('backoff_count', 0)
            cache.set('backoff_last', 0)

        now = time.time()
        # if it hasn't been 5 minutes, increment the wait value
        backoff_last = cache.get('backoff_last')
        if backoff_last and (now - backoff_last) < 300:
            cache.incr('backoff_count')
        else:
            cache.set('backoff_count', 1)

        cache.set('backoff_last', now)

        self.log_warn('Backoff value increased to %.1fs: %s', self._get_backoff(), e)

    # -----------------------------------------------------------------------

    def get_cursor(self, db='default'):
        """
        Get a database connection cursor for db.
        """
        return connections[db].cursor()

    # -----------------------------------------------------------------------

    def parse_api_date(self, apidate, tzd=False):
        """
        Parse a date from API XML into a datetime object.
        """
        if not tzd:
            return datetime.datetime.strptime(apidate, '%Y-%m-%d %H:%M:%S')
        else:
            return datetime.datetime.strptime(apidate, '%Y-%m-%dT%H:%M:%SZ')

    def parse_esi_date(self, esidate):
        import email.utils as eut
        return datetime.datetime(*eut.parsedate(esidate)[:6])

    # -----------------------------------------------------------------------
    # Logging shortcut functions :v
    def log_error(self, text, *args):
        text = '[%s] %s' % (self.__class__.__name__, text)
        # self._logger.error(text, *args)

    def log_warn(self, text, *args):
        text = '[%s] %s' % (self.__class__.__name__, text)
        # self._logger.warn(text, *args)

    def log_info(self, text, *args):
        text = '[%s] %s' % (self.__class__.__name__, text)
        # self._logger.info(text, *args)

    def log_debug(self, text, *args):
        text = '[%s] %s' % (self.__class__.__name__, text)
        # self._logger.debug(text, *args)