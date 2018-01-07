from django.conf import settings
from django.conf.urls import patterns, include, url


# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    # Admin
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    (r'^admin/', include(admin.site.urls)),

    # Authentication things
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', name="auth_login"),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}, name="auth_logout"),
    url(r'^accounts/register/$', 'thing.views.account_register')
)

urlpatterns += patterns(
    'pgsus.views',
    #url(r'^$', 'index', name='index'),
    url(r'^$', 'index', name='index'),
    url(r'^stats$', 'stats', name='stats'),
    url(r'^buyback$', 'buyback', name='buyback'),
    url(r'^freighter$', 'freighter', name='freighter'),
    url(r'^fuel$', 'fuel', name='fuel'),
    url(r'^pricer$', 'pricer', name='pricer'),
    url(r'^overpriced$', 'overpriced', name='overpriced'),
    url(r'^assets', 'assets', name='assets'),
    url(r'^seeding$', 'seedlist', name='seedlist'),
    url(r'^seeding/edit', 'seededit', name='seededit'),
    url(r'^seeding/view', 'seedview', name='seedview'),
    url(r'^contractseeding$', 'contractseedlist', name='contractseedlist'),
    url(r'^contractseeding/edit', 'contractseededit', name='contractseededit'),
    url(r'^contractseeding/view', 'contractseedview', name='contractseedview'),
    url(r'^refineries', 'refinerylist', name='refinerylist'),
    url(r'^api/waypoint', 'add_waypoint', name='add_waypoint'),
    url(r'^perms', 'perms', name='perms'),
    url(r'^mooncomp', 'mooncomp', name='mooncomp'),
    url(r'^extractions', 'extractions', name='extractions')
)

urlpatterns += patterns(
    'thing.views',
    url(r'^thing/$', 'home', name='home'),
    (r'^thing/account/$', 'account'),
    (r'^thing/account/change_password/$', 'account_change_password'),
    (r'^thing/account/oauth_callback/$', 'account_oauth_callback'),
    (r'^thing/account/sso_remove/$', 'account_sso_remove'),
    (r'^thing/account/settings/$', 'account_settings'),
    (r'^thing/account/apikey/add/$', 'account_apikey_add'),
    (r'^thing/account/apikey/delete/$', 'account_apikey_delete'),
    (r'^thing/account/apikey/edit/$', 'account_apikey_edit'),
    (r'^thing/account/apikey/purge/$', 'account_apikey_purge'),
    (r'^thing/account/skillplan/add/$', 'account_skillplan_add'),
    (r'^thing/account/skillplan/delete/$', 'account_skillplan_delete'),
    (r'^thing/account/skillplan/edit/$', 'account_skillplan_edit'),

    (r'^thing/poswatch/$', 'poswatch'),

    (r'^thing/assets/$', 'assets_summary'),
    (r'^thing/assets/filter/$', 'assets_filter'),

    url(r'^thing/blueprints/$', 'blueprints', name='blueprints'),
    (r'^thing/blueprints/add/$', 'blueprints_add'),
    (r'^thing/blueprints/del/$', 'blueprints_del'),
    (r'^thing/blueprints/edit/$', 'blueprints_edit'),
    (r'^thing/blueprints/export/$', 'blueprints_export'),
    (r'^thing/blueprints/import/$', 'blueprints_import'),

    (r'^thing/bpcalc/$', 'bpcalc'),

    (r'^thing/character/(?P<character_name>[\w\'\- ]+)/$', 'character_sheet'),
    (r'^thing/character/(?P<character_name>[\w\'\- ]+)/settings/', 'character_settings'),
    (r'^thing/character/(?P<character_name>[\w\'\- ]+)/mastery/', 'character_mastery'),
    (r'^thing/character/(?P<character_name>[\w\'\- ]+)/skillplan/(?P<skillplan_id>\d+)$', 'character_skillplan'),
    (r'^thing/character_anon/(?P<anon_key>[a-z0-9]+)/$', 'character_anonymous',),
    (r'^thing/character_anon/(?P<anon_key>[a-z0-9]+)/mastery/', 'character_anonymous_mastery'),
    (r'^thing/character_anon/(?P<anon_key>[a-z0-9]+)/skillplan/(?P<skillplan_id>\d+)$', 'character_anonymous_skillplan'),

    (r'^thing/contracts/', 'contracts'),
    (r'^thing/courier_contracts/', 'courier_contracts'),
    (r'^thing/item_contracts/', 'item_contracts'),

    (r'^thing/events/$', 'events'),

    (r'^thing/industry/$', 'industry'),

    (r'^thing/mail/$', 'mail'),
    (r'^thing/mail/json/body/(?P<message_id>\d+)/$', 'mail_json_body'),
    (r'^thing/mail/json/headers/$', 'mail_json_headers'),
    (r'^thing/mail/mark_read/$', 'mail_mark_read'),

    (r'^thing/orders/$', 'orders'),

    (r'^thing/trade/$', 'trade'),
    (r'^thing/trade/(?P<year>\d{4})-(?P<month>\d{2})/$', 'trade_timeframe'),
    (r'^thing/trade/(?P<period>all)/$', 'trade_timeframe'),
    (r'^thing/trade/(?P<slug>[-\w]+)/$', 'trade_timeframe'),

    (r'^thing/transactions/$', 'transactions'),

    (r'^thing/wallet_journal/$', 'wallet_journal'),
    (r'^thing/wallet_journal/aggregate/$', 'wallet_journal_aggregate'),

    (r'^thing/pi/$', 'pi'),
)

if getattr(settings, 'ENABLE_GSFAPI', None):
    urlpatterns += patterns('', (r'^gsfapi/', include('gsfapi.urls')))
