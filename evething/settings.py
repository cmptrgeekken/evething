# Django settings for evething project.
from __future__ import absolute_import

import os
_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = None

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(_PATH, 'tempstatic')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(_PATH, 'static'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = ')%)w42n83ndwvlrnj99-77@e0)(kcs!$zd%#pcy0&e5x0kwq01'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'jingo.Loader',
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'thing.middleware.LastSeenMiddleware',
)

ROOT_URLCONF = 'evething.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(_PATH, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
     'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'mptt',
    'thing',
    'pgsus',
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': [],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

LOGIN_REDIRECT_URL = '/'

# email address that server mails appear to be from
SERVER_EMAIL = 'evething@wafflemonster.org'

# Auth profile thing
AUTH_PROFILE_MODULE = 'thing.UserProfile'

# Themes
THEMES = [
    ('default', '<Default>'),
    ('yeti', 'Yeti'),
    ('darkthing', 'DarkThing'),
    ('cerulean', 'Cerulean'),
    ('cosmo', 'Cosmo'),
    ('cyborg', 'Cyborg'),
    ('slate', 'Slate'),
]

# Jingo setup
JINGO_EXCLUDE_APPS = (
    'admin',
    'admindocs',
    'context_processors',
)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.CachedStaticFilesStorage'

# Allow new users to register, provide a default here so if people upgrade
# without updating local_settings, it won't error
ALLOW_REGISTRATION = False

# Default stagger APITask calls on startup
STAGGER_APITASK_STARTUP = True

# Default URL to use for pricing information, to be overridden in local_settings.py
# but we want to provide a default for those upgrading who havent added this
# to local_settings.
PRICE_URL = 'http://goonmetrics.com/api/price_data/?station_id=60003760&type_id=%s'

# load local settings
from .local_settings import *  # NOPEP8
MANAGERS = ADMINS
TEMPLATE_DEBUG = DEBUG

# Rename the default queue
from kombu import Exchange, Queue

# We're not using rate limits so might as well disable them to save some CPU
CELERY_DISABLE_RATE_LIMITS = True
# Set a soft task time limit of 5 minutes
CELERYD_TASK_SOFT_TIME_LIMIT = 60*30
# Set the prefetch multiplier to 1 so super slow tasks aren't breaking everything
CELERYD_PREFETCH_MULTIPLIER = 1
# We don't care about the results of tasks
CELERY_IGNORE_RESULT = True
# We do care about errors though
CELERY_STORE_ERRORS_EVEN_IF_IGNORED = True
# Set up our queues
CELERY_DEFAULT_QUEUE = 'et_medium'
CELERY_QUEUES = (
    Queue('et_high', Exchange('et_high'), routing_key='et_high'),
    Queue('et_medium', Exchange('et_medium'), routing_key='et_medium'),
    Queue('et_avg_calc', Exchange('et_avg_calc'), routing_key='et_avg_calc'),
    Queue('et_history', Exchange('et_history'), routing_key='et_history'),
    Queue('et_notifications', Exchange('et_notifications'), routing_key='et_notifications'),
    Queue('et_assets', Exchange('et_assets'), routing_key='et_assets'),
    Queue('et_journal', Exchange('et_journal'), routing_key='et_journal'),
    Queue('et_corp_contracts', Exchange('et_corp_contracts'), routing_key='et_corp_contracts'),
    Queue('et_contractseeding', Exchange('et_contractseeding'), routing_key='et_contractseeding'),
    Queue('et_public_contracts', Exchange('et_public_contracts'), routing_key='et_public_contracts'),
    Queue('et_moons', Exchange('et_moons'), routing_key='et_moons'),
    Queue('et_structs', Exchange('et_structs'), routing_key='et_structs'),
    Queue('et_roles', Exchange('et_roles'), routing_key='et_roles'),
    Queue('et_prices', Exchange('et_prices'), routing_key='et_prices'),
    Queue('et_universe', Exchange('et_universe'), routing_key='et_universe'),
    Queue('et_fix_names', Exchange('et_fix_names'), routing_key='et_fix_names'),
    Queue('et_charcorps', Exchange('et_charcorps'), routing_key='et_charcorps')
)

# Periodic tasks
from datetime import timedelta
from celery.schedules import crontab
from thing import queries


CELERYBEAT_SCHEDULE = {
    # spawn tasks every 30 seconds
    #'task_spawner': {
    #    'task': 'thing.task_spawner',
    #    'schedule': timedelta(seconds=10),
    #    'options': {
    #        'expires': 9,
    #        'queue': 'et_high',
    #    },
    #    'args': (),
    #},
    # clean up various table messes every 5 minutes
    'table_cleaner': {
        'task': 'thing.table_cleaner',
        'schedule': timedelta(minutes=5),
        'options': {
            'queue': 'et_high',
        },
        'args': (),
    },

    'avg_calculator': {
        'task': 'thing.avg_calculator',
        'schedule': crontab(hour=0, minute=0),
        'options': {
            'expires': 239*60,
            'queue': 'et_avg_calc',
        },
        'args': (),
    },

    'history_updater': {
        'task': 'thing.history_updater',
        'schedule': timedelta(hours=6),
        'options': {
            'expires': 239*60,
            'queue': 'et_history',
        },
        'args': [],
    },

    'notifications_updater': {
        'task': 'thing.esi_notifications',
        'schedule': timedelta(minutes=10),
        'options': {
            'expires': 240 * 60,
            'queue': 'et_notifications'
        },
        'args': [],
    },
    'asset_updater': {
        'task': 'thing.esiassets',
        'schedule': timedelta(minutes=30),
        'options': {
            'expires': 240 * 60,
            'queue': 'et_assets'
        },
        'args': [],
    },
    'journal_updater': {
        'task': 'thing.esijournal',
        'schedule': timedelta(minutes=60),
        'options': {
            'expires': 240 * 60,
            'queue': 'et_journal'
        },
        'args': [],
    },
    'corp_contract_updater': {
        'task': 'thing.esi_contracts',
        'schedule': timedelta(minutes=5),
        'options': {
            'expires': 240*60,
            'queue': 'et_corp_contracts'
        },
        'args': [],
    },
    'contractseeding': {
        'task': 'thing.esi_contractseeding',
        'schedule': timedelta(minutes=60),
        'options': {
            'expires': 240*60,
            'queue': 'et_contractseeding'
        },
        'args': [],
    },
    'public_contract_updater': {
        'task': 'thing.esi_publiccontracts',
        'schedule': timedelta(minutes=30),
        'options': {
            'expires': 240*60,
            'queue': 'et_public_contracts'
        },
        'args': [],
    },
    'corp_moon_updater': {
        'task': 'thing.moonextraction',
        'schedule': timedelta(minutes=30),
        'options': {
            'expires': 240 * 60,
            'queue': 'et_moons'
        },
        'args': [],
    },
    'corp_struct_updater': {
        'task': 'thing.structures',
        'schedule': timedelta(hours=1),
        'options': {
            'expires': 240 * 60,
            'queue': 'et_structs'
        },
        'args': [],
    },
    'corp_moon_observer': {
        'task': 'thing.moonobserver',
        'schedule': timedelta(hours=1),
        'options': {
            'expires': 240 * 60,
            'queue': 'et_moons'
        },
        'args': [],
    },
    'char_roles_updater': {
        'task': 'thing.characterroles',
        'schedule': crontab(hour=1),
        'options': {
            'expires': 240 * 60,
            'queue': 'et_roles'
        },
        'args': [],
    },
    'price_updater': {
        'task': 'thing.price_updater',
        'schedule': timedelta(minutes=20),
        'options': {
            'expires': 10 * 60,
            'queue': 'et_prices'
        },
        'args': [],
    },

    'universe': {
        'task': 'thing.esiuniverse',
        'schedule': crontab(hour=12),
        'options': {
            'expires': 10 * 60,
            'queue': 'et_universe'
        },
        'args': [],
    },


    # update unknown character/corporation names every hour
    'fix-names': {
        'task': 'thing.fix_names',
        'schedule': timedelta(minutes=30),
        'options': {
            'expires': 59 * 60,
            'queue': 'et_fix_names'
        },
        'args': (),
    },
    'charcorps': {
        'task': 'thing.char_corp_update',
        'schedule': timedelta(minutes=5),
        'options': {
            'expires': 59 * 60,
            'queue': 'et_charcorps'
        },
        'args': (),
    },
    # fix contracts that changed state after they went off Contract.xml
    #'fix_contracts': {
    #    'task': 'thing.fix_contracts',
    #    'schedule': timedelta(minutes=45),
    #    'options': {
    #        'queue': 'et_medium',
    #    },
    #    'args': (),
    #}
}

class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return 'notmigrations'

MIGRATION_MODULES = DisableMigrations()
