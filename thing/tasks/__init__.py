# flake8: noqa
# Internal tasks
from purgeapikey import purge_api_key
from tablecleaner import table_cleaner
from taskspawner import task_spawner

# APIKey tasks
#from accountbalance import AccountBalance
#from accountstatus import AccountStatus
#from apikeyinfo import APIKeyInfo
#from assetlist import AssetList
#from characterinfo import CharacterInfo
#from charactersheet import CharacterSheet
#from citadels import Citadels
from esi_contracts import EsiContracts
from esi_contractseeding import EsiContractSeeding
from esi_publiccontracts import EsiPublicContracts
#from corporationsheet import CorporationSheet
#from industryjobs import IndustryJobs
#from industryjobscurrent import IndustryJobsCurrent
#from locations import Locations
#from mailinglists import MailingLists
#from mailbodies import MailBodies
#from mailmessages import MailMessages
#from marketorders import MarketOrders
# from membertracking import MemberTracking
# from shareholders import Shareholders
#from skillqueue import SkillQueue
#from standings import Standings
#from walletjournal import WalletJournal
#from wallettransactions import WalletTransactions
#from planetarycolonies import PlanetaryColonies
#from planetarypins import PlanetaryPins

# Global API tasks
#from alliancelist import AllianceList
#from conquerablestationlist import ConquerableStationList
#from reftypes import RefTypes
#from serverstatus import ServerStatus
#from sovereignty import Sovereignty

# Periodic tasks
from fixnames import FixNames
from historyupdater import HistoryUpdater
from priceupdater import PriceUpdater
from fixcontracts import FixContracts
from avgcalculator import AvgCalculator
from periodicqueryrunner import PeriodicQueryRunner

#from poswatch import PosWatch
from bookmarks import Bookmarks

from esi_moonextraction import EsiMoonExtraction
from esi_assets import EsiAssets
from esi_characterroles import EsiCharacterRoles
from esi_journal import EsiJournal
from esi_moonobserver import EsiMoonObserver
from esi_notifications import EsiNotifications
from esi_structures import EsiStructures
from esi_universe import EsiUniverse
from esi_systems import EsiSystems
from char_corp_update import CharCorpUpdate
