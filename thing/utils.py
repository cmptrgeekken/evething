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
import json, re
import traceback

from Queue import Queue
from threading import Thread

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
    _session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1000))
    _session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1000))

    _taskstate = None

    global_wait_until = None


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
            return False

        self._api_log.append((url, time.time() - start))

        # If the status code is bad return False
        if not r.status_code == requests.codes.ok:
            return False

        return data

    def fetch_batch_esi_urls(self, urls, character=None, method='get', body=None, headers_to_return=None, access_token=None, batch_size=10):
        shared_dict = dict()

        if character.sso_access_token is None \
                or character.sso_token_expires <= datetime.datetime.utcnow():
            access_token, character.sso_token_expires = self.get_access_token(character)

        def do_batch():
            while True:
                url = q.get()
                response = self.fetch_esi_url(url, character, method, body, headers_to_return, access_token)
                shared_dict[url] = response
                q.task_done()

        q = Queue(len(urls))
        for i in range(batch_size):
            t = Thread(target=do_batch)
            t.daemon = True
            t.start()

        try:
            for url in urls:
                q.put(url)
            q.join()
        except KeyboardInterrupt:
            return

        return shared_dict

    def fetch_esi_url(self, url, character=None, method='get', body=None, headers_to_return=None, access_token=None):
        """
        Fetch an ESI URL
        """

        cache_key = self._get_cache_key(url, {})
        cached_data = cache.get(cache_key)
        headers = cache.get('%s_headers' % cache_key) or dict()

        retry = 3

        key_headers = {'expires', 'date', 'x-esi-error-limit-remain', 'x-esi-error-limit-reset'}

        response = None

        data = None

        _cache_delta = 60

        if cached_data is None:
            start = time.time()
            while retry > 0:
                try:
                    if ApiHelper.global_wait_until is not None\
                            and ApiHelper.global_wait_until > datetime.datetime.now():
                        wait_seconds = (ApiHelper.global_wait_until - datetime.datetime.now()).seconds
                        print('Waiting out error timer for %d seconds' % wait_seconds)
                        time.sleep(wait_seconds)

                    if character is not None:
                        if character.sso_access_token is None\
                                or character.sso_token_expires <= datetime.datetime.utcnow():
                            access_token, character.sso_token_expires = self.get_access_token(character)

                        if access_token is None:
                            if headers_to_return:
                                return False, data, headers
                            return False, data
                    
                    if access_token is not None:
                        response = self._session.request(method, url + '&token=' + access_token, json=body)
                    else:
                        response = self._session.request(method, url, json=body)

                    if response.status_code > 500\
                            and retry > 0:
                        retry -= 1
                        continue

                    data = response.text

                    if headers_to_return is not None:
                        for header in headers_to_return:
                            key_headers.add(header.lower())

                    for header in response.headers:
                        lookup = header.lower()
                        if lookup in key_headers:
                            headers[lookup] = response.headers[header]

                    if 'x-esi-error-limit-remain' in headers \
                            and headers['x-esi-error-limit-remain'] == 1:
                        ApiHelper.global_wait_until = datetime.datetime.now() + datetime.timedelta(seconds=int(headers['x-esi-error-limit-reset']))
                    else:
                        ApiHelper.global_wait_until = None

                    current = self.parse_esi_date(headers['date'])
                    if 'expires' in response.headers:
                        until = self.parse_esi_date(headers['expires'])
                    else:
                        until = datetime.datetime.now() + datetime.timedelta(hours=1)

                    headers['status'] = response.status_code

                    _cache_delta = until - current

                    break
                except Exception, e:
                    retry -= 1
                    traceback.print_exc(e)

                    if retry <= 0:
                        if headers_to_return:
                            return False, data, headers
                        return False, data

            self._api_log.append((url, time.time() - start))

            if response is None or response.status_code > 299:
                if headers_to_return:
                    return False, data, headers
                return False, data
        else:
            data = cached_data

        if method == 'put':
            if headers_to_return:
                return True, data, headers
            return True, data

        if data:
            if cached_data is None:
                cache_expires = total_seconds(_cache_delta) + 10

                if cache_expires >= 0:
                    cache.set(cache_key, data, cache_expires)
                    cache.set('%s_headers' % cache_key, headers, cache_expires)

        if headers_to_return:
            return True, data, headers
        return True, data

    # -----------------------------------------------------------------------

    def parse_xml(self, data):
        """
        Parse XML and return an ElementTree.
        """
        return ET.fromstring(data.encode('utf-8'))

    def get_access_token(self, character):
        oauth_handler = self.oauth_handler()

        response = oauth_handler.get_token("", grant_type='refresh_token', refresh_token=character.sso_refresh_token)
        if response is not None and 'access_token' in response:
            #character.sso_error_count = 0
            #character.save()
            return response['access_token'], datetime.datetime.now() + datetime.timedelta(
                seconds=response['expires_in'])

        if 'error' in response and response['error'] == 'invalid_token':
            character.sso_error_count += 1
            if character.sso_error_count >= 3:
                # Deauthorize the user
                print('Deauthorizing user %s' % character.name)
                character.deauthorize_user()
            character.save()

        return None, None

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
