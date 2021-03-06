# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

corporation_wallets = """
SELECT  cw.corporation_id, c.name, cw.account_key, cw.description, cw.balance
FROM    thing_corpwallet cw
INNER JOIN thing_corporation c ON c.id = cw.corporation_id
WHERE   corporation_id IN (
    SELECT  DISTINCT c.corporation_id
    FROM    thing_character c
    INNER JOIN thing_apikey ak ON c.apikey_id = ak.id
    WHERE ak.user_id = %s
)
ORDER BY c.name, cw.account_key
"""

marketgroup_all_items = """
SELECT i.id
FROM thing_marketgroup mg
INNER JOIN thing_item i on mg.id = i.market_group_id
WHERE mg.lft >= %d and mg.rght < %d and mg.tree_id = %d
"""

fuel_block_industry = """
SELECT i.name AS name,SUM(runs)*40 AS qty
FROM thing_industryjob ij 
INNER JOIN thing_item i ON ij.product_id=i.id
WHERE status IN (1,3) and activity=1 and i.name LIKE '%Fuel Block' group by i.name
ORDER BY i.name
"""


order_aggregation = """
SELECT  mo.creator_character_id,
        c.name,
        COUNT(mo.order_id) AS orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NULL THEN 1 END), 0) AS personal_orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NOT NULL THEN 1 END), 0) AS corp_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN 1 THEN 1 END), 0) AS buy_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN 1 THEN mo.total_price END), 0) AS total_buys,
        COALESCE(SUM(CASE mo.buy_order WHEN 0 THEN 1 END), 0) AS sell_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN 0 THEN mo.total_price END), 0) AS total_sells,
        COALESCE(SUM(mo.escrow), 0) AS total_escrow
FROM    thing_marketorder mo,
        thing_character c,
        thing_apikey_characters ac,
        thing_apikey a
WHERE   mo.creator_character_id = c.id
        AND c.id = ac.character_id
        AND ac.apikey_id = a.id
        AND a.corporation_id IS NULL
        AND a.user_id = %s
GROUP BY mo.creator_character_id, c.name
ORDER BY c.name
"""

# BPCalc movement calculation
bpcalc_movement = """
SELECT  item_id, CAST(SUM(movement) / 30 * %%s AS decimal(18,2))
FROM    thing_pricehistory
WHERE   item_id IN (%s)
        AND date >= %%s
GROUP BY item_id
"""

# item_ids for a specific user's BlueprintInstance objects and related components
user_item_ids = """
SELECT  bp.item_id
FROM    thing_blueprint bp, thing_blueprintinstance bpi
WHERE   bp.id = bpi.blueprint_id
        AND bpi.user_id = %s
UNION
SELECT  item_id
FROM    thing_blueprintcomponent
WHERE   blueprint_id IN (
            SELECT  blueprint_id
            FROM    thing_blueprintinstance
            WHERE   user_id = %s
)
UNION
SELECT  ca.item_id
FROM    thing_asset ca, thing_character c, thing_apikey_characters ac, thing_apikey a,
        thing_item i, thing_itemgroup ig
WHERE   ca.character_id = c.id
        AND c.id = ac.character_id
        AND ac.apikey_id = a.id
        AND a.user_id = %s
        AND ca.item_id = i.id
        AND i.item_group_id = ig.id
        AND ig.category_id != 9
"""

# item_ids for all BlueprintInstance objects and related components
# Commenting out old query until blueprints are functional again
'''all_item_ids = """
SELECT  bp.item_id
FROM    thing_blueprint bp, thing_blueprintinstance bpi
WHERE   bp.id = bpi.blueprint_id
UNION
SELECT  item_id
FROM    thing_blueprintcomponent
WHERE   blueprint_id IN (
            SELECT  blueprint_id
            FROM    thing_blueprintinstance
)
UNION
SELECT  a.item_id
FROM    thing_asset a, thing_item i, thing_itemgroup ig
WHERE   a.item_id = i.id
        AND i.item_group_id = ig.id
        AND ig.category_id != 9
""" '''
all_item_ids = """
SELECT a.item_id AS item_id FROM thing_asset a
UNION
SELECT ci.item_id AS item_id FROM thing_contractitem ci
UNION
SELECT ij.product_id AS item_id FROM thing_industryjob ij
UNION
SELECT t.item_id AS item_id FROM thing_transaction t
"""

pricing_item_ids = """
SELECT  DISTINCT pw.item_id, 10000002 AS region_id
FROM    thing_pricewatch pw
WHERE   pw.active = 1
UNION
select distinct i.id as item_id, 10000002 as region_id
FROM thing_item i
	inner join thing_marketgroup mg on i.market_group_id=mg.id
where 
	(exists (select 1 from thing_buybackitem where item_id=i.id and accepted=1)
    or exists (select 1 from thing_buybackitem bi inner join thing_marketgroup mg1 on bi.market_group_id=mg1.id WHERE mg1.lft<=mg.lft and mg1.rght >= mg.rght and mg1.tree_id=mg.tree_id and accepted=1))
    and not exists (select 1 from thing_buybackitem where item_id=i.id and accepted=0)
    and not exists (select 1 from thing_buybackitem bi inner join thing_marketgroup mg1 on bi.market_group_id=mg1.id WHERE mg1.lft<=mg.lft and mg1.rght >= mg.rght and mg1.tree_id=mg.tree_id and accepted=0)
"""

''' Add if we want all local stuff
UNION
SELECT DISTINCT so.item_id, c.region_id
FROM thing_stationorder so
    INNER JOIN thing_station s ON so.station_id=s.id
    INNER JOIN thing_system sy ON s.system_id=sy.id
    INNER JOIN thing_constellation c ON sy.constellation_id=c.id
    WHERE s.name NOT LIKE 'Jita%'
'''

journal_aggregate_char = """
SELECT  EXTRACT(YEAR FROM date) AS year,
        EXTRACT(MONTH FROM date) AS month,
        EXTRACT(DAY FROM date) AS day,
        ref_type_id,
        SUM(CASE WHEN (amount > 0) THEN amount ELSE 0 END) AS income,
        SUM(CASE WHEN (amount < 0) THEN amount ELSE 0 END) as expense
FROM    thing_journalentry
WHERE   character_id = %s
        AND corp_wallet_id IS NULL
GROUP BY year, month, day, ref_type_id
"""

journal_aggregate_corp = """
SELECT  EXTRACT(YEAR FROM date) AS year,
        EXTRACT(MONTH FROM date) AS month,
        EXTRACT(DAY FROM date) AS day,
        ref_type_id,
        SUM(CASE WHEN (amount > 0) THEN amount ELSE 0 END) AS income,
        SUM(CASE WHEN (amount < 0) THEN amount ELSE 0 END) as expense
FROM    thing_journalentry
WHERE   character_id = %s
        AND corp_wallet_id = %s
GROUP BY year, month, day, ref_type_id
"""


# taskmeta stuff
task_summary_generic = """
SELECT  EXTRACT(YEAR FROM date_done) AS y,
        EXTRACT(MONTH FROM date_done) AS m,
        EXTRACT(DAY FROM date_done) AS d,
        EXTRACT(HOUR FROM date_done) AS h,
        COUNT(*) AS count
FROM    celery_taskmeta
GROUP BY y, m, d, h
ORDER BY y, m, d, h
"""

task_summary_sqlite = """
SELECT  strftime('%Y', date_done) as y,
        strftime('%m', date_done) as m,
        strftime('%d', date_done) as d,
        strftime('%H', date_done) as h,
        COUNT(*) AS count
FROM    celery_taskmeta
GROUP BY y, m, d, h
ORDER BY y, m, d, h
"""

# asset stuff
asset_delete_char = """
DELETE
FROM    thing_asset
WHERE   character_id = %s
        AND corporation_id = 0
"""

asset_delete_corp = """
DELETE
FROM    thing_asset
WHERE   corporation_id = %s
"""

assetsummary_delete_char = """
DELETE
FROM    thing_assetsummary
WHERE   character_id = %s
        AND corporation_id = 0
"""

assetsummary_delete_corp = """
DELETE
FROM    thing_assetsummary
WHERE   corporation_id = %s
"""

# skillqueue stuff
skillqueue_delete = """
DELETE
FROM    thing_skillqueue
WHERE   character_id = %s
"""


# statistics
fuelblock_purchase_contracts = """
SELECT DISTINCT c.contract_id
FROM thing_contract c 
    INNER JOIN thing_contractitem ci ON c.id=ci.contract_id
    INNER JOIN thing_item i ON ci.item_id=i.id 
WHERE c.type IN('item_exchange', 'Item Exchange')
    AND i.name LIKE '%Fuel Block'
    AND ((c.corporation_id=c.issuer_corp_id AND ci.included=1)
          OR (c.assignee_id=c.corporation_id AND ci.included=0))
"""

fuelblock_monthly_purchase_summary = """
SELECT DATE_FORMAT(c.date_completed, '%m-%Y') AS month, SUM(ci.quantity) AS qty
FROM thing_contract c 
    INNER JOIN thing_contractitem ci ON c.id=ci.contract_id
    INNER JOIN thing_item i ON ci.item_id=i.id 
WHERE c.type IN ('item_exchange', 'Item Exchange')
    AND i.name LIKE '%Fuel Block'
    AND ((c.corporation_id=c.issuer_corp_id AND ci.included=1)
          OR (c.assignee_id=c.corporation_id AND ci.included=0))
    AND c.date_completed IS NOT NULL
  GROUP BY DATE_FORMAT(c.date_completed, '%m-%Y')
  ORDER BY DATE_FORMAT(c.date_completed, '%m-%Y');
"""

courier_contracts = """
SELECT DISTINCT c.contract_id
FROM thing_contract c
INNER JOIN thing_corporation co on co.id=c.assignee_id
WHERE c.assignee_id=co.id
AND c.type = 'Courier'
AND co.name = 'Penny''s Flying Circus'
"""

buyback_contracts = """
    SELECT DISTINCT c.contract_id
    FROM thing_contract c
         inner join thing_corporation co on c.assignee_id=co.id
    WHERE
        c.type in ('Item Exchange', 'item_exchange')
        AND c.issuer_corp_id != co.id
        AND co.name = 'Penny''s Flying Circus'

"""

buyback_item_summary = """
SELECT i1.name, SUM(ci1.quantity)
FROM thing_contract c1
    INNER JOIN thing_contractitem ci1 ON c1.contract_id=ci1.contract_id
    INNER JOIN thing_item i1 ON ci1.item_id=i1.id
WHERE
    c1.contract_id IN (%s)
    AND EXISTS (SELECT 1 FROM thing_pricewatch pw WHERE pw.item_id=ci1.item_id AND pw.active=1)
GROUP BY i1.name
""" % buyback_contracts

fuelblock_purchase_stats = """
SELECT i.name,
       SUM(ci.quantity) AS quantity,
       DATE_FORMAT(MIN(c.date_issued), '%m-%d-%Y') AS start_date
FROM thing_contract c 
    INNER JOIN thing_contractitem ci ON c.id=ci.contract_id
    INNER JOIN thing_item i ON ci.item_id=i.id 
WHERE c.type IN ('item_exchange', 'Item Exchange') 
    AND c.status = 'Completed'
    AND i.name LIKE '%Fuel Block'
    AND ((c.corporation_id=c.issuer_corp_id AND ci.included=1)
          OR (c.assignee_id=c.corporation_id AND ci.included=0))
GROUP BY i.name
"""

fuelblock_purchase_ttl = """
SELECT i.name,
       SUM(ci.quantity) AS quantity,
       SUM(c.reward)+SUM(c.price) AS ttl_reward,
       COUNT(c.contract_id) AS ttl_contracts,
       DATE_FORMAT(MIN(c.date_issued), '%m-%d-%Y') AS start_date,
       AVG(TO_DAYS(c.date_completed)-TO_DAYS(c.date_issued))*24*60*60 AS avg_completion_secs
FROM thing_contract c 
    INNER JOIN thing_contractitem ci ON c.id=ci.contract_id
    INNER JOIN thing_item i ON ci.item_id=i.id 
WHERE c.type IN ('item_exchange', 'Item Exchange') 
    AND c.status = 'Completed'
    AND i.name LIKE '%Fuel Block'
    AND ((c.corporation_id=c.issuer_corp_id AND ci.included=1)
          OR (c.assignee_id=c.corporation_id AND ci.included=0))
"""

fuelblock_stock = """
SELECT i.name, a.quantity, s.name 
FROM thing_asset a 
    INNER JOIN thing_item i ON a.item_id=i.id 
    INNER JOIN thing_station s ON s.id = a.station_id 
WHERE i.name like '%Fuel Block' 
GROUP BY by i.name,s.name
ORDER BY s.name,i.name
"""

fuelblock_component_stock = """
SELECT i.name, a.quantity, a.inv_flag_id, s.name
FROM thing_asset a
    INNER JOIN thing_item i ON a.item_id=i.id
    INNER JOIN thing_station s ON s.id = a.station_id
WHERE i.id IN (SELECT item_id FROM thing_pricewatch WHERE price_group != '')
    AND inv_flag_id=117
GROUP BY i.name,s.name
ORDER BY s.name,i.name
"""

fuelblock_pending_stats = """
SELECT i.name,SUM(ci.quantity) AS quantity
FROM thing_contract c 
    INNER JOIN thing_contractitem ci ON c.id=ci.contract_id
    INNER JOIN thing_item i ON ci.item_id=i.id 
WHERE c.type IN ('item_exchange', 'Item Exchange') 
    AND c.status = 'Outstanding'
    AND i.name LIKE '%Fuel Block'
    AND ((c.corporation_id=c.issuer_corp_id AND ci.included=1)
          OR (c.assignee_id=c.corporation_id AND ci.included=0))
GROUP BY i.name
"""

fuelblock_job_stats = """
SELECT i.name,SUM(ij.runs)*bp.count AS quantity
FROM thing_industryjob ij 
    INNER JOIN thing_item i ON ij.product_id=i.id 
    INNER JOIN thing_blueprintproduct bp ON ij.blueprint_id=bp.blueprint_id AND ij.product_id=bp.item_id
WHERE ij.status = 1
    AND i.name LIKE '%Fuel Block'
GROUP BY i.name
"""

courier_completed_stats = """
SELECT
    DATE_FORMAT(MIN(c.date_issued), '%m-%d-%Y') AS start_date,
    SUM(c.volume) AS ttl_volume,
	SUM(c.collateral) AS ttl_collateral,
	SUM(c.reward) AS ttl_reward,
	COUNT(*) AS ttl_contracts,
	COUNT(DISTINCT c.issuer_char_id) AS distinct_users,
	AVG(TO_DAYS(c.date_accepted)-TO_DAYS(c.date_issued))*24*60*60 AS avg_acceptance_secs,
	AVG(TO_DAYS(c.date_completed)-TO_DAYS(c.date_accepted))*24*60*60 AS avg_completion_secs
FROM thing_contract c
WHERE c.assignee_id=c.corporation_id
AND c.status = 'Completed'
AND c.type = 'Courier'
"""

courier_pending_stats = """
SELECT
    SUM(c.volume) AS ttl_volume,
	SUM(c.collateral) AS ttl_collateral,
	SUM(c.reward) AS ttl_reward,
	COUNT(*) AS ttl_contracts,
	COUNT(DISTINCT c.issuer_char_id) AS distinct_users,
	AVG(TO_DAYS(CURRENT_TIMESTAMP)-TO_DAYS(c.date_issued))*24*60*60 AS avg_age_secs,
	AVG(TO_DAYS(c.date_completed)-TO_DAYS(c.date_issued))*24*60*60 AS avg_completion_secs
FROM thing_contract c
WHERE c.assignee_id=c.corporation_id
AND c.status IN ('Outstanding', 'InProgress')
AND c.type = 'Courier'
"""

buyback_completed_stats = """
SELECT 
    DATE_FORMAT(MIN(c.date_issued), '%m-%d-%Y') AS start_date,
	SUM(c.price) AS ttl_price,
	COUNT(*) AS ttl_contracts,
	COUNT(DISTINCT c.issuer_char_id) AS distinct_users,
	AVG(TO_DAYS(c.date_completed)-TO_DAYS(c.date_issued))*24*60*60 AS avg_completion_secs	
FROM thing_contract c
WHERE c.assignee_id=c.corporation_id
AND c.status = 'Completed'
AND c.type IN ('item_exchange', 'Item Exchange')
AND c.issuer_corp_id != c.corporation_id
AND EXISTS
	(SELECT 1 
	 FROM thing_contractitem ci 
		INNER JOIN thing_pricewatch pw ON ci.item_id=pw.item_id 
	 WHERE ci.contract_id=c.id AND ci.included=1 AND pw.active=1)
"""

buyback_pending_stats = """
SELECT 
	SUM(c.price) AS ttl_price,
	COUNT(*) AS ttl_contracts,
	COUNT(DISTINCT c.issuer_char_id) AS distinct_users,
	AVG(TO_DAYS(CURRENT_TIMESTAMP)-TO_DAYS(c.date_issued))*24*60*60 AS avg_age_secs	
FROM thing_contract c
WHERE c.assignee_id=c.corporation_id
AND c.status = 'Outstanding'
AND c.type IN ('item_exchange', 'Item Exchange')
AND c.issuer_corp_id != c.corporation_id
AND EXISTS
	(SELECT 1 
	 FROM thing_contractitem ci 
		INNER JOIN thing_pricewatch pw ON ci.item_id=pw.item_id 
	 WHERE ci.contract_id=c.id AND ci.included=1 AND pw.active=1)
"""


summary_shipping_costs = """
SELECT MIN(date_issued),SUM(reward),SUM(collateral),SUM(volume),ch.name 
FROM thing_contract c
    INNER JOIN thing_station s ON s.id=c.end_station_id
    INNER JOIN thing_character ch ON c.assignee_id=ch.id 
WHERE c.issuer_corp_id=c.corporation_id 
    AND type='Courier' 
    AND s.name like 'B-9C24 -%' 
GROUP BY ch.name
"""

summary_buyback_purchases = """
SELECT contract_id 
FROM thing_contract 
WHERE contract_id IN (SELECT DISTINCT c.contract_id
   FROM thing_contract c
   WHERE c.assignee_id=c.corporation_id
   AND c.type IN ('item_exchange', 'Item Exchange')
   AND c.issuer_corp_id != c.corporation_id
   AND EXISTS (SELECT 1 FROM thing_contractitem ci INNER JOIN thing_pricewatch pw ON ci.item_id=pw.item_id WHERE ci.contract_id=c.id AND ci.included=1 AND pw.active=1)
) and price = 0
"""

contract_check_script = """
select count(*) from (select MIN(id),contract_id,count(*) from thing_contract group by contract_id having count(*) > 1) c
"""

contract_fix_script = """
delete from thing_contract where id IN (select MIN(id) from thing_contract group by contract_id having count(*) > 1);
"""

contractitem_check_script = """
select count(*) 
from (select contract_id,item_id,quantity from thing_contractitem group by contract_id,item_id,quantity having count(*) > 1) c;
"""

contractitem_fix_script = """
delete from thing_contractitem 
where id in (select MIN(id) from thing_contractitem group by contract_id,item_id,quantity having count(*) > 1);
"""

industry_job_slots = """
select name, group_name,
	research_slots_active,research_slots_max-research_slots_active AS research_slots_avail,research_slots_max,research_slots_deliverable,
	mfg_slots_active,mfg_slots_max-mfg_slots_active AS mfg_slots_avail, mfg_slots_max,mfg_slots_deliverable,
	industry_level,adv_industry_level,me_time_level,te_time_level,copy_time_level,
	mfg_time_implant,me_time_implant,te_time_implant,copy_time_implant,reprocessing_implant,
	max_research_jumps, max_mfg_jumps,
        reaction_slots_active,reaction_slots_max-reaction_slots_active AS reaction_slots_avail, reaction_slots_max,reaction_slots_max,reaction_slots_deliverable,
        (1+reaction_level*.04)-1 AS reaction_time_bonus,
	(1+industry_level*.04)*(1+adv_industry_level*.03)*(1+mfg_time_implant)-1 AS mfg_time_bonus,
	(1+adv_industry_level*.03)*(1+me_time_level*.05)*(1+me_time_implant)-1 AS me_time_bonus,
	(1+adv_industry_level*.03)*(1+te_time_level*.05)*(1+te_time_implant)-1 AS te_time_bonus,
	(1+adv_industry_level*.03)*(1+copy_time_level*.05)*(1+copy_time_implant)-1 AS copy_time_bonus 
FROM
(SELECT c.name,
		(select ak.group_name from thing_apikey_characters akc inner join thing_apikey ak ON  akc.apikey_id=ak.id WHERE akc.character_id=c.id limit 1) AS group_name,
	   if(alo.level=0,0,COALESCE(1+lo.level+alo.level,0)) AS research_slots_max,
	   (SELECT COUNT(*) FROM thing_industryjob ij WHERE ij.installer_id=c.id AND ij.activity IN(3,4,5,8) AND ij.status=1) AS research_slots_active,
	   (SELECT COUNT(*) FROM thing_industryjob ij WHERE ij.installer_id=c.id AND ij.activity IN(3,4,5,8) AND ij.status=1 AND ij.end_date <= NOW()) AS research_slots_deliverable,
	   if(amp.level=0,0,COALESCE(1+mp.level+amp.level,0)) AS mfg_slots_max,
	   (SELECT COUNT(*) FROM thing_industryjob ij WHERE ij.installer_id=c.id AND ij.activity=1 AND ij.status=1) AS mfg_slots_active,
	   (SELECT COUNT(*) FROM thing_industryjob ij WHERE ij.installer_id=c.id AND ij.activity=1 AND ij.status=1 AND ij.end_date <= NOW()) AS mfg_slots_deliverable,
           (SELECT COUNT(*) FROM thing_industryjob ij WHERE ij.installer_id=c.id AND ij.activity=9 AND ij.status=1) AS reaction_slots_active,
           (SELECT COUNT(*) FROM thing_industryjob ij WHERE ij.installer_id=c.id AND ij.activity=9 AND ij.status=1 AND ij.end_date <= NOW()) AS reaction_slots_deliverable,
           if(mr.level<4,0,COALESCE(1+mr.level+amr.level,0)) AS reaction_slots_max,
           COALESCE(r.level, 0) AS reaction_level, -- *.04
	   COALESCE(ind.level,0) AS industry_level, -- *.04
	   COALESCE(ai.level,0) AS adv_industry_level, -- *.03
	   COALESCE(my.level,0) AS me_time_level, -- *.05
	   COALESCE(rs.level,0) AS te_time_level, -- *.05
	   COALESCE(sc.level,0) AS copy_time_level, -- *.05
	   --((1 + ind.level * .04)*(1 + ai.level*.03)) AS mfg_time_bonus,
	   -- ((1 + ai.level*.03)*(1 + my.level*.05)) AS me_time_bonus,
	   --((1 + ai.level*.03)*(1 + rs.level*.05)) AS te_time_bonus,
	   --((1 + ai.level*.03)*(1 + sc.level*.05)) AS copy_time_bonus,
	   COALESCE(sn.level,0) * 5 AS max_research_jumps,
	   COALESCE(scm.level,0) * 5 AS max_mfg_jumps,
	   COALESCE((SELECT CAST(SUBSTR(name, -2) AS UNSIGNED)*.01 FROM thing_item WHERE id=impi.implant_id),0) AS mfg_time_implant,
	   COALESCE((SELECT CAST(SUBSTR(name, -2) AS UNSIGNED)*.01 FROM thing_item WHERE id=impm.implant_id),0) AS me_time_implant,
	   COALESCE((SELECT CAST(SUBSTR(name, -2) AS UNSIGNED)*.01 FROM thing_item WHERE id=impr.implant_id),0) AS reprocessing_implant,
	   COALESCE((SELECT CAST(SUBSTR(name, -2) AS UNSIGNED)*.01 FROM thing_item WHERE id=imprs.implant_id),0) AS te_time_implant,
	   COALESCE((SELECT CAST(SUBSTR(name, -2) AS UNSIGNED)*.01 FROM thing_item WHERE id=impsc.implant_id),0) AS copy_time_implant
	FROM thing_character c
		LEFT JOIN thing_characterskill lo ON lo.character_id=c.id AND lo.skill_id=3406 -- Laboratory Operations
		LEFT JOIN thing_characterskill alo ON alo.character_id=c.id AND alo.skill_id=24624 -- Advanced Laboratory Operations
		LEFT JOIN thing_characterskill mp ON mp.character_id=c.id AND mp.skill_id=3387 -- Mass Production
		LEFT JOIN thing_characterskill amp ON amp.character_id=c.id AND amp.skill_id=24625 -- Advanced Mass Production
		LEFT JOIN thing_characterskill my ON my.character_id=c.id AND my.skill_id=3409 -- Metallurgy
		LEFT JOIN thing_characterskill sc ON sc.character_id=c.id AND sc.skill_id=3402 -- Science
		LEFT JOIN thing_characterskill rs ON rs.character_id=c.id AND rs.skill_id=3403 -- Research
		LEFT JOIN thing_characterskill ai ON ai.character_id=c.id AND ai.skill_id=3388 -- Advanced Industry
		LEFT JOIN thing_characterskill ind ON ind.character_id=c.id AND ind.skill_id=3380 -- Industry
		LEFT JOIN thing_characterskill sn ON sn.character_id=c.id AND sn.skill_id=24270 -- Scientific Networking
		LEFT JOIN thing_characterskill scm ON scm.character_id=c.id AND scm.skill_id=24268 -- Scientific Networking
		LEFT JOIN thing_characterdetails_implants impi ON impi.characterdetails_id=c.id AND impi.implant_id in (27170, 27167, 27171) -- Industry
		LEFT JOIN thing_characterdetails_implants impm ON impm.characterdetails_id=c.id AND impm.implant_id in (27182, 27176, 27181) -- Metallurgy
		LEFT JOIN thing_characterdetails_implants impr ON impr.characterdetails_id=c.id AND impr.implant_id in (27175, 27169, 27174) -- Reprocessing
		LEFT JOIN thing_characterdetails_implants imprs ON imprs.characterdetails_id=c.id AND imprs.implant_id in (27180, 27177, 27179) -- Research
		LEFT JOIN thing_characterdetails_implants impsc ON impsc.characterdetails_id=c.id AND impsc.implant_id in (27185, 27178, 27184) -- Science
                LEFT JOIN thing_characterskill mr ON mr.character_id=c.id AND mr.skill_id=45748 -- Mass Reactions
                LEFT JOIN thing_characterskill amr ON amr.character_id=c.id AND amr.skill_id=45749 -- Advanced Mass Reactions
                LEFT JOIN thing_characterskill r ON r.character_id=c.id AND r.skill_id=45746 -- Reactions
	WHERE alo.level > 0 OR amp.level > 0 OR amr.level > 0
    ORDER BY group_name, name) details
    ORDER BY details.group_name, details.name;
"""

stationorder_ids_to_update = """
SELECT so.order_id FROM thing_stationorder so
INNER JOIN thing_stationorderupdater sou ON so.order_id=sou.order_id
WHERE so.volume_remaining > sou.volume_remaining OR so.price != sou.price
"""

stationorder_seeding_qty = """
select i.id, 
       s.id AS station_id,
       i.name AS item_name,
       s.name AS station_name,
       iss.min_qty,SUM(so.volume_remaining) AS volume_remaining,
       SUM(so.price*so.volume_remaining)/SUM(so.volume_remaining) AS avg_price
    FROM thing_itemstationseed iss 
    INNER JOIN thing_item i ON iss.item_id=i.id
    INNER JOIN thing_station s ON iss.station_id=s.id
    LEFT JOIN thing_stationorder so ON iss.station_id=so.station_id and iss.item_id=so.item_id and so.buy_order=0
    WHERE iss.list_id=%s
    GROUP BY iss.item_id,s.id
    ORDER BY s.name, i.name
"""

stationorder_seeding_breakdown = """
SELECT *,
    ROUND(jita_min_price+jita_shipping, 2) AS jita_price_plus_shipping,
    ROUND((jita_min_price+jita_shipping)*1.025*1.02, 2) AS imported_price,
    ROUND((jita_min_price+jita_shipping)*1.025*1.02*1.2, 2) AS twentypct_profit,
    CAST((avg_price / ((jita_min_price + jita_shipping)*1.025*1.02)) * 10000 AS UNSIGNED)/100 AS overpriced_pct
FROM (
SELECT
   i.id AS item_id,
   s.id as station_id,
   c.region_id AS region_id,
   ic.name AS category,
   ig.name AS grp,
   i.name AS item_name,
   s.name AS station_name,
   iss.min_qty AS min_qty,
   COUNT(so.order_id) AS active_order_count,
   COALESCE(AVG(so.times_updated),0) AS avg_order_updates,
   COALESCE(AVG(DATEDIFF(NOW(),so.issued)),0) AS avg_order_age,
   COALESCE(AVG(so.times_updated / DATEDIFF(NOW(),so.issued)),0) AS avg_updates_per_day,
   COALESCE(SUM(so.volume_remaining),0) AS volume_remaining,
   COALESCE(ROUND(SUM(so.volume_remaining*so.price)/SUM(so.volume_remaining), 2),0) AS avg_price,
   (SELECT MIN(jso.price) FROM thing_stationorder jso WHERE jso.item_id=i.id AND jso.station_id=60003760 AND jso.buy_order=0) AS jita_min_price,
   (SELECT SUM(jso.volume_remaining) FROM thing_stationorder jso WHERE jso.item_id=i.id AND jso.station_id=60003760 AND jso.buy_order=0) AS jita_current_volume,
   COALESCE(i.sell_fivepct_price,0) AS fivepct_price, 
   COALESCE(MAX(pm.cross_region_collateral), 0.02) AS shipping_collateral,
   COALESCE(MAX(pm.cross_region_m3), 400) AS shipping_m3,
   ROUND(i.sell_fivepct_price*COALESCE(MAX(pm.cross_region_collateral), 0.02)+IF(i.packaged_volume > 0,i.packaged_volume,i.volume)*COALESCE(MAX(pm.cross_region_m3), 400), 2) AS jita_shipping
FROM thing_itemstationseed iss
LEFT JOIN thing_stationorder so ON iss.item_id=so.item_id AND iss.station_id=so.station_id AND so.buy_order=0
LEFT JOIN thing_station s ON s.id=iss.station_id
LEFT JOIN thing_system sy ON s.system_id=sy.id
LEFT JOIN thing_constellation c ON sy.constellation_id=c.id
LEFT JOIN thing_item i ON iss.item_id=i.id
LEFT JOIN thing_itemgroup ig ON i.item_group_id=ig.id
LEFT JOIN thing_itemcategory ic ON ig.category_id=ic.id
LEFT JOIN thing_marketgroup mg1 ON i.market_group_id=mg1.id
LEFT JOIN (SELECT fs.system_id, MAX(cross_region_collateral) AS cross_region_collateral, MAX(cross_region_m3) AS cross_region_m3 FROM thing_freightersystem fs INNER JOIN thing_freighterpricemodel pm ON fs.price_model_id=pm.id AND pm.is_thirdparty = 1 INNER JOIN thing_freightersystem fs2 ON fs2.price_model_id=pm.id AND fs2.system_id=30000142 GROUP BY fs.system_id) pm ON pm.system_id = s.system_id
WHERE iss.list_id=%s
GROUP BY iss.item_id, iss.station_id
) o
ORDER BY station_name, item_name;

"""




stationorder_analysis = """
SELECT so.id, 
    so.name, 
    so.order_ct AS sell_order_ct, 
    so.market_volume as sell_market_volume,
    so.min_price AS sell_min_price,
    so.avg_price AS sell_avg_price,
    bo.order_ct as buy_order_ct,
    bo.market_volume as buy_market_volume,
    bo.max_price as buy_max_price,
    bo.avg_price AS buy_avg_price
FROM
(SELECT
    i.id,
    i.name, 
    count(*) AS order_ct,  
    SUM(so.volume_remaining) AS market_volume,
    SUM(so.volume_remaining*so.price) / SUM(so.volume_remaining) AS avg_price,
    MAX(price) as max_price,
    MIN(price) AS min_price 
FROM thing_stationorder so 
    INNER JOIN thing_item i ON so.item_id=i.id 
    INNER JOIN thing_station s ON so.station_id=s.id 
WHERE s.name like 'Jita%' AND so.price > .01 AND buy_order=0
GROUP BY so.item_id) so,
(SELECT
    i.id,
    i.name, 
    count(*) AS order_ct,  
    SUM(so.volume_remaining) AS market_volume,
    SUM(so.volume_remaining*so.price) / SUM(so.volume_remaining) AS avg_price,
    MAX(price) as max_price,
    MIN(price) AS min_price
FROM thing_stationorder so 
    INNER JOIN thing_item i ON so.item_id=i.id 
    INNER JOIN thing_station s ON so.station_id=s.id 
WHERE s.name like 'Jita%' AND so.price > .01 AND buy_order=1
GROUP BY so.item_id) bo
WHERE so.id = bo.id
"""

stationorder_overpriced_base_query = """
SELECT    
   i.id AS item_id, 
   s.id as station_id, 
   ic.name AS category, 
   ig.name AS grp, 
   i.name AS item_name,
   s.name AS station_name,  
   iss.min_qty AS min_qty,
   COUNT(so.order_id) AS active_order_count,
   COALESCE(ROUND(AVG(so.times_updated),2),0) AS avg_order_updates,
   COALESCE(AVG(DATEDIFF(NOW(),so.issued)),0) AS avg_order_age,
   COALESCE(ROUND(AVG(so.times_updated / DATEDIFF(NOW(),so.issued)),2),0) AS avg_updates_per_day,
   COALESCE(SUM(so.volume_remaining),0) AS volume_remaining,
   COALESCE(ROUND(SUM(so.volume_remaining*so.price)/SUM(so.volume_remaining), 2),0) AS avg_price,
   (SELECT MIN(jso.price) FROM thing_stationorder jso WHERE jso.item_id=i.id AND jso.station_id=60003760 AND jso.buy_order=0) AS jita_min_price,
   COALESCE(i.sell_fivepct_price,0) AS fivepct_price, 
   COALESCE(ROUND(pm.cross_region_collateral,2), 0.02) AS shipping_collateral,
   COALESCE(pm.cross_region_m3, 400) AS shipping_m3,
   ROUND(i.sell_fivepct_price*COALESCE(pm.cross_region_collateral, 0.02)+i.volume*COALESCE(pm.cross_region_m3, 400), 2) AS jita_shipping,
   ph30.thirtyday_vol AS thirtyday_vol,
   ph30.thirtyday_orders AS thirtyday_order,
   ph5.fiveday_vol AS fiveday_vol,
   ph5.fiveday_orders AS fiveday_order 
FROM thing_itemstationseed iss
LEFT JOIN thing_stationorder so ON iss.item_id=so.item_id AND iss.station_id=so.station_id
LEFT JOIN thing_station s ON s.id=iss.station_id
LEFT JOIN thing_system sy ON s.system_id=sy.id
LEFT JOIN thing_constellation c ON sy.constellation_id=c.id
LEFT JOIN thing_item i ON iss.item_id=i.id
LEFT JOIN thing_itemgroup ig ON i.item_group_id=ig.id
LEFT JOIN thing_itemcategory ic ON ig.category_id=ic.id
LEFT JOIN thing_marketgroup mg1 ON i.market_group_id=mg1.id
LEFT JOIN thing_view_pricehistory_thirtyday ph30 ON ph30.item_id=i.id AND ph30.region_id=c.region_id
LEFT JOIN thing_view_pricehistory_fiveday ph5 ON ph5.item_id=i.id AND ph5.region_id=c.region_id
LEFT JOIN thing_view_stationorder_stdev stdev ON i.id=stdev.item_id and s.id=stdev.station_id
LEFT JOIN thing_freightersystem fs ON fs.system_id=s.system_id
LEFT JOIN thing_freighterpricemodel pm ON fs.price_model_id=pm.id AND pm.is_thirdparty=1
LEFT JOIN thing_freightersystem fs2 ON fs2.price_model_id=pm.id AND fs2.system_id=30000142
WHERE so.price IS NULL OR (so.buy_order=0 AND so.price < stdev.avg_price + 2 * stdev.stdev)
GROUP BY iss.item_id, iss.station_id
"""

stationorder_overpriced = """
SELECT *, 
    ROUND(jita_min_price+jita_shipping, 2) AS jita_price_plus_shipping, 
    ROUND((jita_min_price+jita_shipping)*1.025*1.02, 2) AS imported_price,
    ROUND((jita_min_price+jita_shipping)*1.025*1.02*1.2, 2) AS twentypct_profit,
    CAST((avg_price / ((jita_min_price + jita_shipping)*1.025*1.02)) * 10000 AS UNSIGNED)/100 AS overpriced_pct
FROM (""" + stationorder_overpriced_base_query + """
    ) o 
"""

stationorder_localprice_truncate = """
TRUNCATE TABLE `thing_cache_localprice`;
"""

stationorder_localprice_update = """
INSERT INTO `thing_cache_localprice`
%s;""" % stationorder_overpriced

stationorder_overpriced_cached = """
SELECT iss.*,
	   lp.category,
       lp.grp,
       lp.item_name,
       lp.station_name, lp.min_qty,
       lp.active_order_count,
       lp.avg_order_updates,
       lp.avg_order_age, 
       lp.avg_updates_per_day,
       lp.volume_remaining,
       lp.avg_price,
       lp.jita_min_price,
       lp.fivepct_price,
       lp.shipping_collateral,
       lp.shipping_m3,
       lp.jita_shipping,
       lp.thirtyday_vol,
       lp.thirtyday_order,
       lp.fiveday_vol,
       lp.fiveday_order,
       lp.jita_price_plus_shipping,
       lp.imported_price,
       lp.twentypct_profit,
       lp.overpriced_pct
FROM thing_itemstationseed iss 
    LEFT JOIN thing_cache_localprice lp ON iss.item_id=lp.item_id AND iss.station_id=lp.station_id
WHERE iss.list_id=%s
ORDER BY station_name, item_name"""

stationorder_localprice_create = """
CREATE TABLE `thing_cache_localprice` (
  `item_id` int(11) NOT NULL,
  `station_id` bigint(20) NOT NULL,
  `category` varchar(64) NOT NULL,
  `grp` varchar(128) NOT NULL,
  `item_name` varchar(128) NOT NULL,
  `station_name` varchar(128) NOT NULL,
  `min_qty` int(11) NOT NULL,
  `active_order_count` int(11) NOT NULL,
  `avg_order_updates` decimal(20,2) NOT NULL,
  `avg_order_age` int(11) NOT NULL,
  `avg_updates_per_day` decimal(20,2) NOT NULL,
  `volume_remaining` decimal(20,0) DEFAULT NULL,
  `avg_price` decimal(20,2) DEFAULT NULL,
  `jita_min_price` decimal(20,2) NOT NULL,
  `fivepct_price` decimal(20,2) NOT NULL,
  `shipping_collateral` decimal(20,2) NOT NULL,
  `shipping_m3` int(11) NOT NULL,
  `jita_shipping` decimal(20,2) NOT NULL DEFAULT '0.00',
  `thirtyday_vol` decimal(20,0) DEFAULT NULL,
  `thirtyday_order` decimal(20,0) DEFAULT NULL,
  `fiveday_vol` decimal(20,0) DEFAULT NULL,
  `fiveday_order` decimal(20,0) DEFAULT NULL,
  `jita_price_plus_shipping` decimal(20,2) NOT NULL DEFAULT '0.00',
  `imported_price` decimal(20,2) NOT NULL DEFAULT '0.00',
  `twentypct_profit` decimal(20,2) NOT NULL DEFAULT '0.00',
  `overpriced_pct` decimal(20,2) DEFAULT NULL,
  PRIMARY KEY (`item_id`,`station_id`),
  KEY `avg_price_idx` (`avg_price`),
  KEY `jita_import_price_idx` (`imported_price`),
  KEY `overage_pct_idx` (`overpriced_pct`),
  KEY `volume_idx` (`volume_remaining`),
  KEY `fiveday_order_idx` (`fiveday_order`),
  KEY `fiveday_volume_idx` (`fiveday_vol`),
  KEY `thirtyday_order_idx` (`thirtyday_order`),
  KEY `thirtyday_volume_idx` (`thirtyday_vol`),
  KEY `group_idx` (`grp` ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
"""

bulk_stationorder_create_tmp = """
CREATE TABLE thing_stationorder_tmp LIKE thing_stationorder;
"""

bulk_stationorder_drop_tmp = """
DROP TABLE IF EXISTS thing_stationorder_tmp;
"""

bulk_stationorder_tmp_insert = """
INSERT IGNORE INTO thing_stationorder_tmp (`order_id`,`item_id`,`station_id`,`volume_entered`,`volume_remaining`,`minimum_volume`,`price`,`buy_order`,`issued`,`expires`,`range`,`last_updated`,`times_updated`)
    VALUES %s;
"""

bulk_stationorder_delete = """
DELETE FROM thing_stationorder WHERE station_id IN (%s) AND NOT EXISTS(select 1 FROM thing_stationorder_tmp sot WHERE sot.order_id=thing_stationorder.order_id);
"""

bulk_stationorder_insert = """
INSERT IGNORE INTO thing_stationorder (`order_id`,`item_id`,`station_id`,`volume_entered`,`volume_remaining`,`minimum_volume`,`price`,`buy_order`,`issued`,`expires`,`range`,`last_updated`,`times_updated`) 
SELECT sot.order_id, sot.item_id, sot.station_id, sot.volume_entered, sot.volume_remaining, sot.minimum_volume, sot.price, sot.buy_order, sot.issued, sot.expires, sot.range, sot.last_updated, sot.times_updated from thing_stationorder_tmp sot LEFT JOIN thing_stationorder so ON sot.order_id=so.order_id AND sot.station_id=so.station_id  WHERE so.order_id IS NULL;
"""

bulk_stationorder_update = """
UPDATE thing_stationorder so INNER JOIN thing_stationorder_tmp sot ON so.order_id=sot.order_id SET so.volume_remaining=sot.volume_remaining,so.price=sot.price, so.last_updated=sot.last_updated, so.times_updated=IF(so.price!=sot.price,so.times_updated+1,so.times_updated);
"""

bulk_stationorders_insert_update = """
INSERT INTO thing_stationorder (`order_id`,`item_id`,`station_id`,`volume_entered`,`volume_remaining`,`minimum_volume`,`price`,`buy_order`,`issued`,`expires`,`range`,`last_updated`,`times_updated`)
    VALUES %s 
ON DUPLICATE KEY UPDATE 
    last_updated=NOW(),
    times_updated=IF(price!=VALUES(price),times_updated+1,times_updated), 
    price=VALUES(price),
    volume_remaining=VALUES(volume_remaining)"""

bulk_assets_create_tmp = """
DROP TABLE IF EXISTS thing_esiasset_tmp;
CREATE TEMPORARY TABLE thing_esiasset_tmp LIKE thing_esiasset;
"""

bulk_assets_tmp_insert = """
INSERT IGNORE INTO thing_esiasset_tmp(`character_id`, `corporation_id`, `item_id`, `type_id`, `is_singleton`, `is_blueprint_copy`, `location_flag`, `location_id`, `location_type`, `quantity`, `last_updated`)
   VALUES %s
"""

bulk_assets_tmp_merge = """
DELETE FROM thing_esiasset WHERE corporation_id=%d AND NOT EXISTS (SELECT 1 FROM thing_esiasset_tmp eat WHERE eat.item_id=thing_esiasset.item_id);  
UPDATE thing_esiasset ea INNER JOIN thing_esiasset_tmp eat ON ea.item_id=eat.item_id SET ea.character_id=eat.character_id, ea.corporation_id=eat.corporation_id, ea.location_flag=eat.location_flag, ea.location_id=eat.location_id, ea.location_type=eat.location_type, ea.quantity=eat.quantity,ea.last_updated=eat.last_updated;
INSERT INTO thing_esiasset SELECT eat.* from thing_esiasset_tmp eat LEFT JOIN thing_esiasset ea ON eat.item_id=ea.item_id WHERE ea.item_id IS NULL;
"""

bulk_assets_insert_update = """
INSERT INTO thing_esiasset(`character_id`, `corporation_id`, `item_id`, `type_id`, `is_singleton`, `is_blueprint_copy`, `location_flag`, `location_id`, `location_type`, `quantity`, `last_updated`)
   VALUES %s
ON DUPLICATE KEY UPDATE
   character_id=VALUES(character_id),
   corporation_id=VALUES(corporation_id),
   location_flag=VALUES(location_flag),
   location_id=VALUES(location_id),
   location_type=VALUES(location_type),
   quantity=VALUES(quantity),
   last_updated=VALUES(last_updated)
"""

bulk_journal_insert = """

INSERT IGNORE INTO thing_esijournal(`journal_id`, `amount`, `balance`, `context_id`, `context_id_type`, `date`, `description`, `first_party_id`, `reason`, `ref_type`, `second_party_id`, `corporation_id`, `wallet_id`) VALUES %s
"""


order_updatemarketorders = """
update thing_marketorder mo INNER JOIN thing_stationorder so ON mo.order_id=so.order_id SET mo.price=so.price, mo.volume_remaining=so.volume_remaining
"""

order_calculateshipping = """
    SELECT COALESCE(IF(i.packaged_volume > 0, i.packaged_volume,i.volume) * CASE WHEN stdest.id=storig.id THEN 0
                     WHEN sydest.id=syorig.id THEN in_system_m3
                     WHEN cdest.region_id=corig.region_id THEN in_region_m3
                     ELSE cross_region_m3 END
           + %s * CASE WHEN stdest.id=storig.id THEN 0
                       WHEN sydest.id=syorig.id THEN in_system_collateral
                       WHEN cdest.region_id=corig.region_id THEN in_region_collateral
                       ELSE cross_region_collateral END
           + CASE WHEN stdest.id=storig.id THEN 0
                  WHEN sydest.id=syorig.id THEN in_system_base
                  WHEN cdest.region_id=corig.region_id THEN in_region_base
                  ELSE cross_region_base END 
           , 0) AS shipping_cost
    FROM thing_freighterpricemodel pm
        INNER JOIN thing_freightersystem fsdest ON pm.id=fsdest.price_model_id
        INNER JOIN thing_freightersystem fsorig ON pm.id=fsorig.price_model_id
        INNER JOIN thing_system sydest ON fsdest.system_id=sydest.id
        INNER JOIN thing_system syorig ON fsorig.system_id=syorig.id
        INNER JOIN thing_constellation cdest ON sydest.constellation_id=cdest.id
        INNER JOIN thing_constellation corig ON syorig.constellation_id=corig.id
        INNER JOIN thing_station stdest ON fsdest.system_id=stdest.system_id
        INNER JOIN thing_station storig ON fsorig.system_id=storig.system_id
        JOIN thing_item i
    WHERE i.id=%s
          AND stdest.id=%s
          AND storig.id=%s
    LIMIT 1
"""

order_calculateshipping_breakdown = """
    SELECT COALESCE(CASE WHEN stdest.id=storig.id THEN 0
                     WHEN sydest.id=syorig.id THEN in_system_m3
                     WHEN cdest.region_id=corig.region_id THEN in_region_m3
                     ELSE cross_region_m3 END, 0) AS shipping_m3,
           COALESCE(CASE WHEN stdest.id=storig.id THEN 0
                       WHEN sydest.id=syorig.id THEN in_system_collateral
                       WHEN cdest.region_id=corig.region_id THEN in_region_collateral
                       ELSE cross_region_collateral END, 0) AS shipping_collateral,
           COALESCE(CASE WHEN stdest.id=storig.id THEN 0
                  WHEN sydest.id=syorig.id THEN in_system_base
                  WHEN cdest.region_id=corig.region_id THEN in_region_base
                  ELSE cross_region_base END 
           , 0) AS shipping_base
    FROM thing_freighterpricemodel pm
        INNER JOIN thing_freightersystem fsdest ON pm.id=fsdest.price_model_id
        INNER JOIN thing_freightersystem fsorig ON pm.id=fsorig.price_model_id
        INNER JOIN thing_system sydest ON fsdest.system_id=sydest.id
        INNER JOIN thing_system syorig ON fsorig.system_id=syorig.id
        INNER JOIN thing_constellation cdest ON sydest.constellation_id=cdest.id
        INNER JOIN thing_constellation corig ON syorig.constellation_id=corig.id
        INNER JOIN thing_station stdest ON fsdest.system_id=stdest.system_id
        INNER JOIN thing_station storig ON fsorig.system_id=storig.system_id
    WHERE stdest.id=%s
          AND storig.id=%s
    LIMIT 1
"""

industryjob_active_items_summary = """
SELECT i.name,
       SUM(ij.runs)*bp.count 
FROM thing_industryjob ij 
	INNER JOIN thing_item i ON ij.product_id=i.id
	INNER JOIN thing_blueprintproduct bp ON bp.blueprint_id=ij.blueprint_id AND bp.item_id=i.id
WHERE ij.status=1 AND ij.activity=1 AND bp.activity=1
GROUP BY i.name
"""

poswatch_taxman_subquery = """
SELECT
    ph.corp_id,
    c.name AS corp_name,
    c.forum_handle,
    c.discord_handle,
    md.item_name AS moon_name,
    COALESCE(ak.apikeyinfo_errors, 'No API') AS api_errors,
    COUNT(*)*2000000 AS tax_total,
    COALESCE((SELECT SUM(cd.amount) FROM thing_poswatch_corpdeposit cd WHERE cd.corp_id=ph.corp_id),0) AS tax_paid,
    MIN(online_timestamp) AS min_online,
    MIN(state_timestamp) AS min_state,
    (SELECT DATEDIFF(NOW(), MAX(date)) FROM thing_poswatch_poshistory where corp_id=ph.corp_id AND state in (3,4)) AS days_offline,
    (SELECT COUNT(*) FROM thing_poswatch_poshistory WHERE corp_id=ph.corp_id AND COUNT(*) > 0 GROUP BY date ORDER BY date desc LIMIT 1) AS last_tower_count
FROM thing_poswatch_poshistory ph
    INNER JOIN thing_corporation c ON ph.corp_id=c.id
    INNER JOIN thing_mapdenormalize md ON md.item_id=ph.moon_id
    LEFT JOIN thing_apikey ak ON ak.corporation_id=ph.corp_id
WHERE taxable=1
GROUP BY ph.corp_id
ORDER BY c.name
"""

poswatch_taxman = """
SELECT * FROM (
    SELECT taxes.*, (tax_total-tax_paid) AS tax_remaining, IF(last_tower_count = 0,'<Unknown>', CEILING(30 - ((tax_total - tax_paid) / last_tower_count / 2000000))) AS tax_evict_days 
    FROM (%s) taxes
) taxes
WHERE tax_evict_days <= 15
ORDER BY CAST(tax_evict_days AS SIGNED);
""" % poswatch_taxman_subquery

poswatch_taxman_all = """
SELECT taxes.*,(tax_total-tax_paid) AS tax_remaining, IF(last_tower_count = 0,'<Unknown>', CEILING(30 - ((tax_total - tax_paid) / last_tower_count / 2000000))) AS tax_evict_days 
FROM (%s) taxes;
""" % poswatch_taxman_subquery

poswatch_poshistory_fix = """
SELECT corp_id,type_id,pos_id,state,location_id,DATE_ADD(ph.min_date, INTERVAL n DAY) AS date,moon_id,CAST(taxable AS UNSIGNED)
FROM (SELECT corp_id,type_id,pos_id,state,location_id,DATE(GREATEST(MAX(state_timestamp), MAX(online_timestamp))) AS max_date, DATE(LEAST(MIN(state_timestamp), MIN(online_timestamp))) AS min_date,moon_id,taxable
      FROM thing_poswatch_poshistory
      WHERE taxable=1
            AND state_timestamp IS NOT NULL
            AND (state_timestamp IS NULL OR state_timestamp >= '2016-12-19')  -- Alliance foundation date
            AND (online_timestamp IS NULL OR online_timestamp >= '2016-12-19')
      GROUP BY corp_id,pos_id) ph
    INNER JOIN thing_numbers
WHERE ph.min_date IS NOT NULL
    AND n > 0
    AND n < DATEDIFF(ph.max_date, ph.min_date)
    AND NOT EXISTS (SELECT 1 FROM thing_poswatch_poshistory p WHERE p.corp_id=ph.corp_id and p.pos_id=ph.pos_id AND p.date=DATE_ADD(ph.min_date, INTERVAL n DAY))
    AND corp_id=%d
"""

crazy_contractprice_calculator = """
select final_group.item_name, 
       ROUND(SUM(final_group.ttl_qty), 0) AS ttl_qty,
	   ROUND(SUM(final_group.avg_price * final_group.ttl_qty) / SUM(final_group.ttl_qty), 2) AS avg_price
FROM (
SELECT CASE WHEN imi.name IS NOT NULL THEN imi.name ELSE material_group.item_name END AS item_name,
	   CASE WHEN material_group.material_ratio IS NOT NULL 
				THEN ROUND(imi.sell_fivepct_price * material_group.material_ratio, 2)
			ELSE material_group.avg_price END AS avg_price,
		CASE WHEN material_group.material_ratio IS NOT NULL
				THEN material_group.ttl_qty * im.quantity * .875
			ELSE material_group.ttl_qty END AS ttl_qty
FROM (
SELECT 
	outer_group.*,
    ROUND(outer_group.avg_price / SUM(imi.sell_fivepct_price * (im.quantity / imi.portion_size) * IF(outer_group.item_name LIKE 'Compressed%', .875, 1)), 2) AS material_ratio
FROM (
SELECT 
	inner_group.item_name, 
    inner_group.item_id,
	SUM(inner_group.ttl_qty) AS ttl_qty,
    ROUND(SUM(inner_group.ttl_qty * inner_group.avg_price) / SUM(inner_group.ttl_qty), 2) AS avg_price
FROM (
SELECT cprice.name AS item_name, 
	   cprice.item_id AS item_id,
	SUM(cprice.qty_sold) AS ttl_qty,
	ROUND(SUM(cprice.qty_sold * cprice.item_calculated_price) / SUM(cprice.qty_sold), 2) AS avg_price
FROM 
(SELECT c.contract_id, 
	i.id AS item_id,
	i.name, 
	sc.contract_value AS contract_calculated_price, 
    c.price / sc.contract_value AS contract_ratio,
    c.price AS contract_sold_price,
    i.sell_fivepct_price,
    i.sell_fivepct_price * c.price / sc.contract_value AS item_calculated_price,
    ci.quantity AS qty_sold
FROM thing_contract c
	INNER JOIN 
    (SELECT ci.contract_id, 
			ci.item_id, 
            SUM(ci.quantity) AS quantity
		FROM thing_contractitem ci 
		GROUP BY ci.contract_id, ci.item_id
	) ci ON c.id=ci.contract_id
    INNER JOIN thing_item i ON ci.item_id=i.id
    INNER JOIN
		(
			SELECT 
				sci.contract_id, 
                SUM(sci.quantity*si.sell_fivepct_price) AS contract_value 
			FROM thing_contractitem sci
				INNER JOIN thing_item si ON sci.item_id=si.id
			GROUP BY sci.contract_id
		) sc ON sc.id=ci.contract_id
WHERE c.contract_id IN (SELECT DISTINCT c.contract_id
   FROM thing_contract c
   WHERE c.assignee_id=c.corporation_id
   AND c.type IN ('item_exchange', 'Item Exchange')
   AND c.issuer_corp_id != c.corporation_id
   AND c.status = 'Completed'
   AND EXISTS (SELECT 1 FROM thing_contractitem ci INNER JOIN thing_pricewatch pw ON ci.item_id=pw.item_id WHERE ci.contract_id=c.id AND ci.included=1 AND pw.active=1)
   AND NOT EXISTS (SELECT 1 from thing_contractitem ci WHERE ci.item_id NOT IN (SELECT item_id from thing_pricewatch pw WHERE pw.active=1) AND ci.contract_id=c.id AND ci.included=1)
) and c.price > 0
  --AND c.date_accepted > DATE_ADD(NOW(), INTERVAL -1 MONTH)
    ) AS cprice
GROUP BY cprice.name
UNION
SELECT 
t.item_name,
t.item_id,
SUM(t.ttl_qty) AS ttl_qty,
ROUND(SUM(t.ttl_qty*t.avg_price) / SUM(t.ttl_qty), 2) AS avg_price
FROM
(
select s.name AS station_name, 
	   i.name AS item_name,
       i.id as item_id,
	   SUM(t.quantity) AS ttl_qty,
       SUM(t.quantity*price) / SUM(t.quantity) 
		+ CASE 
			WHEN r.name IN ('Fade', 'Pure Blind') THEN 0 
            ELSE 390 * i.volume + SUM(t.quantity*price) / SUM(t.quantity) * .01
		END AS avg_price
	FROM thing_transaction t 
	INNER JOIN thing_item i ON i.id = t.item_id
    INNER JOIN thing_station s ON s.id = t.station_id
    INNER JOIN thing_system sy ON s.system_id=sy.id
    INNER JOIN thing_constellation con ON sy.constellation_id=con.id
    INNER JOIN thing_region r ON con.region_id=r.id
    INNER JOIN thing_corpwallet cw ON cw.account_id=t.corp_wallet_id
    INNER JOIN thing_corporation c ON cw.corporation_id=c.id
    WHERE t.buy_transaction=1
		AND i.id IN (SELECT item_id FROM thing_pricewatch WHERE active=1)
        AND c.name = 'Penny''s Flying Circus'
        -- AND t.date > DATE_ADD(NOW(), INTERVAL -1 MONTH)
    GROUP BY s.name, i.name
) t
GROUP BY t.item_name
) inner_group
GROUP BY inner_group.item_id
) outer_group
LEFT JOIN thing_itemmaterial im ON im.item_id=outer_group.item_id and im.active=1
LEFT JOIN thing_item imi ON im.material_id=imi.id
WHERE item_name NOT LIKE '%Fuel Block'
GROUP BY outer_group.item_id) material_group
LEFT JOIN thing_itemmaterial im ON im.item_id=material_group.item_id and im.active=1
LEFT JOIN thing_item imi ON im.material_id=imi.id
) final_group
GROUP BY final_group.item_name
"""

closest_celestial = """
SELECT md.item_id
FROM evedb.thing_mapdenormalize md
    INNER JOIN thing_item i ON md.type_id=i.id
    WHERE md.solar_system_id=%s
    ORDER BY POWER(x - %s,2)+POWER(y-%s,2)+POWER(z-%s,2)
    LIMIT 1;
"""

contractseeding_contracts = """
SELECT DISTINCT c.contract_id AS contract_id
FROM thing_contract c
INNER JOIN thing_contractseeding cs ON c.start_station_id=cs.station_id
INNER JOIN
(
SELECT c.contract_id, cs.id AS csid, COUNT(DISTINCT ci.item_id) AS matching_values
FROM thing_contract c
        INNER JOIN thing_contractitem ci ON c.id=ci.contract_id
        INNER JOIN thing_contractseeding cs ON c.start_station_id=cs.station_id
        LEFT JOIN thing_corporation co ON co.id = c.assignee_id
        LEFT JOIN thing_alliance al ON al.id = c.assignee_id
    WHERE 
		ci.item_id IN (SELECT csi.item_id FROM thing_contractseedingitem csi WHERE csi.contractseeding_id=cs.id AND csi.required=1)
        AND c.status='outstanding' 
        AND cs.id = %d
        AND cs.is_active=1
        AND ( (co.id IS NOT NULL and co.alliance_id=99005338) OR (co.id IS NULL AND al.id = 99005338) ) 
    GROUP BY c.contract_id, cs.id) search ON c.contract_id=search.contract_id AND search.csid=cs.id
WHERE 
	cs.id = search.csid
    AND search.matching_values = (SELECT COUNT(*) FROM thing_contractseedingitem csi WHERE csi.contractseeding_id=cs.id AND csi.required=1)
    AND date_expired > NOW()
"""

assetlist_query = """
SELECT
       ea1.item_id AS asset_id,
       COALESCE(sy1.name, sy2.name) AS system_name,
       COALESCE(sy1.id, sy2.id) AS system_id,
	   s.name AS station_name,
       s.id AS station_id,
       ea1.location_flag,
       ea1.is_singleton,
	   i2.name AS parent_name,
       ea1.location_id as parent_id,
       i.name AS item_name,
       ea1.quantity,
       ea1.quantity * (SELECT MIN(so.price) FROM thing_stationorder so where so.buy_order=0 AND so.item_id=i.id AND so.station_id=60003760) AS rough_value,
       ea1.quantity * i.volume AS m3
	from thing_esiasset ea1 
	inner join thing_item i on ea1.type_id=i.id
	LEFT JOIN thing_esiasset ea2 ON ea1.location_id=ea2.item_id
    LEFT JOIN thing_item i2 ON ea2.type_id=i2.id
    LEFT JOIN thing_station s ON s.id = COALESCE(ea2.location_id, ea1.location_id)
    LEFT JOIN thing_system sy1 ON sy1.id = COALESCE(ea2.location_id, ea1.location_id)
    LEFT JOIN thing_system sy2 ON sy2.id = s.system_id
    WHERE %s
    ORDER BY system_name ASC, station_name, parent_id, ea1.location_flag, i.name
"""

assetlist_corporation_query = assetlist_query % "ea1.corporation_id=%s"

assetlist_character_query = assetlist_query % "ea1.character_id=%s"


blueprint_getcomponents = """
SELECT 
	bpci.id AS component_id, 
    bpci.name, 
    bpc.count,
    IF(bpcp.id IS NOT NULL,1,0) AS has_bp
    FROM evedb.thing_blueprint bp 
	inner join thing_blueprintcomponent bpc ON bpc.blueprint_id=bp.id
    inner join thing_item bpci on bpc.item_id=bpci.id
    inner join thing_blueprintproduct bpp on bp.id=bpp.blueprint_id
    inner join thing_item bppi on bpp.item_id=bppi.id
    left join thing_blueprintproduct bpcp ON bpc.item_id=bpcp.item_id
    where bppi.name = %s AND bpc.activity IN (1,11) AND bpp.activity IN (1,11)
"""

moonobserver_getentries = """
select moe.type_id,
       i.name AS ore_name, 
       SUM(moe.quantity) AS quantity,
       SUM(moe.quantity * i.volume) AS mined_m3,
       CASE WHEN 
			i.name LIKE 'Twinkling%%' 
            OR i.name LIKE 'Shining%%' 
            OR i.name LIKE 'Glowing%%' 
            OR i.name LIKE 'Shimmering%%' 
		THEN 1 ELSE 0 END AS is_jackpot
FROM thing_moonobserverentry moe
	INNER JOIN thing_item i on i.id=moe.type_id
where moe.last_updated >= DATE_ADD(NOW(), INTERVAL -2 DAY)
    AND moe.observer_id=%s
GROUP BY moe.observer_id, i.name
"""

contract_fix_duplicate_items = """
DELETE FROM thing_contractitem WHERE id NOT IN (SELECT MIN(id) FROM thing_contractitem group by record_id,contract_id);
"""

jumpbridge_lo_quantity = """
select s.id AS station_id,
       s.name AS station_name,
       COALESCE(jh.lo_quantity,SUM(ea.quantity)) AS lo_qty,
       IF(st.state='hull_reinforce' OR st.state='armor_reinforce', 'Reinforced', 'Active') as state,
       (SELECT IF(ss.state='online',1,0) FROM thing_structureservice ss WHERE ss.structure_id=s.id AND ss.name='Jump Gate Access') AS service_state,
       COALESCE(jh.lo_diff, 0) as lo_diff,
       COALESCE(jh.last_updated,MIN(ea.last_updated)) AS last_updated
FROM thing_station s
    LEFT JOIN thing_esiasset ea ON ea.location_id=s.id AND ea.type_id=16273
    LEFT JOIN thing_item i ON i.id=ea.type_id
    LEFT JOIN thing_jumpgate_history jh ON jh.station_id=s.id
    INNER JOIN thing_corporation c ON s.corporation_id=c.id
    INNER JOIN thing_structure st ON s.id=st.station_id
    LEFT JOIN thing_structureservice ss ON ss.structure_id=s.id
WHERE s.type_id = 35841 AND c.alliance_id=%d AND jh.last_updated = (SELECT MAX(last_updated) FROM thing_jumpgate_history WHERE station_id=s.id) AND s.ignore_jb=0
GROUP BY s.name
ORDER BY jh.lo_quantity ASC
"""

jumpbridge_lo_history_update = """
INSERT IGNORE INTO thing_jumpgate_history(station_id, lo_quantity, lo_diff, last_updated) 
   SELECT jg.station_id, 
          jg.lo_qty,
          jg.lo_qty-COALESCE((SELECT jgh.lo_quantity FROM thing_jumpgate_history jgh WHERE jgh.station_id=jg.station_id AND jgh.last_updated < jg.last_updated ORDER BY jgh.last_updated DESC LIMIT 1),0) as lo_diff,
          jg.last_updated 
   FROM (select s.id AS station_id,
       s.name AS station_name,
       SUM(ea.quantity) AS lo_qty,
       IF(st.state='hull_reinforce' OR st.state='armor_reinforce', 'Reinforced', 'Active') as state,
       (SELECT IF(ss.state='online',1,0) FROM thing_structureservice ss WHERE ss.structure_id=s.id AND ss.name='Jump Gate Access') AS service_state,
       ea.last_updated
FROM thing_station s
    LEFT JOIN thing_esiasset ea ON ea.location_id=s.id AND ea.type_id=16273
    LEFT JOIN thing_item i ON i.id=ea.type_id
    INNER JOIN thing_corporation c ON s.corporation_id=c.id
    INNER JOIN thing_structure st ON s.id=st.station_id
    LEFT JOIN thing_structureservice ss ON ss.structure_id=s.id
WHERE s.type_id = 35841 AND s.ignore_jb=0
GROUP BY s.name) jg
   WHERE NOT EXISTS (SELECT 1 FROM thing_jumpgate_history jgh WHERE jgh.last_updated=jg.last_updated AND jgh.station_id=jg.station_id) AND jg.last_updated IS NOT NULL;
"""

ihub_upgrades = """
select s.name AS system, 
       c.name AS constellation,
       r.name AS region,
       i.name AS upgrade, 
       IF(eai.location_flag='StructureActive', 'Online', 'Offline') AS state,
       a.last_updated AS last_updated,
       co.ticker AS corp_ticker
FROM thing_esiasset a 
    INNER JOIN thing_system s ON a.location_id=s.id
    INNER JOIN thing_constellation c ON s.constellation_id=c.id
    INNER JOIN thing_region r ON c.region_id=r.id
    INNER JOIN thing_esiasset eai ON a.item_id=eai.location_id 
    INNER JOIN thing_item i ON eai.type_id=i.id 
    INNER JOIN thing_corporation co ON a.corporation_id=co.id
    INNER JOIN thing_alliance al ON co.alliance_id=al.id
WHERE a.type_id=32458 AND al.id = %d
ORDER BY s.name, i.name;
"""

lo_station_quantities = """
select s.name AS station_name, sum(a.quantity) AS qty  from thing_esiasset a  inner join thing_item i on a.type_id=i.id  left join thing_esiasset l1 on l1.item_id=a.location_id  left join thing_esiasset l2 on l2.item_id=l1.location_id  left join thing_esiasset l3 on l3.item_id=l2.location_id  left join thing_esiasset l4 on l4.item_id=l3.location_id, thing_station s  where i.name='Liquid Ozone'  and (     (s.id=l1.location_id AND l1.location_type = 'other')     OR (s.id=l2.location_id AND l2.location_type ='other')      OR (s.id=l3.location_id AND l3.location_type = 'other')      OR (s.id=l4.location_id AND l4.location_type = 'other'))  and a.corporation_id IN (SELECT id FROM thing_corporation WHERE alliance_id =%d) AND a.quantity > 10000 group by s.name order by s.name;
"""

current_bridges = """
select jg.id, jg.destination_structure_id AS end_id, st.name as start, e.name as end,
    IF((SELECT MAX(last_updated) FROM thing_jumpgate_history jgh WHERE jgh.station_id=jg.id) > DATE_ADD(NOW(), INTERVAL -1 DAY),1,0) AS start_in_alliance,
    IF((SELECT MAX(last_updated) FROM thing_jumpgate_history jgh WHERE jgh.station_id=jg.destination_structure_id) > DATE_ADD(NOW(), INTERVAL -1 DAY),1,0) as end_in_alliance,
    ea.id as end_alliance_id,
    ea.name as end_alliance_name,
    sa.id as start_alliance_id,
    sa.name as start_alliance_name
    from thing_jumpgates jg
        inner join thing_station es on es.id=jg.destination_structure_id and es.deleted=0
        left join thing_corporation ec on ec.id=es.corporation_id
        left join thing_alliance ea on ec.alliance_id=ea.id
        inner join thing_station s on s.deleted=0 AND s.id=jg.id
        inner join thing_corporation c on s.corporation_id=c.id
        left join thing_alliance sa on c.alliance_id=sa.id
        inner join thing_system st on st.id=jg.system_id
        inner join thing_system e on jg.destination_system_id=e.id
    order by st.name
"""

jumpbridge_usage_fees = """
SELECT j.date, 
       COALESCE(IF(ch.name = '*UNKNOWN*', NULL, ch.name), CONCAT('ID: ', j.first_party_id)) AS `char`,
       COALESCE(IF(co.name='*UNKNOWN*', NULL, co.name), CONCAT('ID: ', ch.corporation_id)) as corp,
       a.name as alliance_name, 
       FORMAT(j.amount,0) as fee,
       COALESCE(st1.name, CONCAT('ID: ', j.context_id)) as gate_name,
       FORMAT(j.amount/200,0) AS lo_used,
       ROUND((amount/200 - 50)/.000003/(SQRT(POW(md1.x-md2.x,2) + POW(md1.y-md2.y,2) + POW(md1.z-md2.z,2))/9460730472580800),0) AS rough_mass,
       (SELECT GROUP_CONCAT(name) FROM thing_item WHERE ABS(rough_mass-mass) / mass < .001 AND published=1 AND market_group_id IS NOT NULL) AS possible_ships
FROM thing_esijournal j 
    LEFT JOIN thing_character ch on ch.id = j.first_party_id 
    LEFT JOIN thing_corporation co ON co.id=ch.corporation_id 
    LEFT JOIN thing_alliance a on co.alliance_id=a.id
    LEFT JOIN thing_station st1 on st1.id=j.context_id
    LEFT JOIN thing_system sy1 ON sy1.name = LEFT(st1.name, POSITION( CHAR(187 using ucs2) IN st1.name) - 2)
    LEFT JOIN thing_system sy2 ON sy2.name = substr(st1.name,(locate(CONCAT(' ', CHAR(187 using ucs2), ' '),st1.name) + 3),((locate(' - ',st1.name) - locate(CONCAT(' ', CHAR(187 using ucs2), ' '),st1.name)) - 3))
    LEFT JOIN thing_mapdenormalize md1 ON md1.item_id=sy1.id
    LEFT JOIN thing_mapdenormalize md2 on md2.item_id=sy2.id
WHERE ref_type='structure_gate_jump' AND j.amount >= %s
ORDER BY date DESC;
"""

in_range_systems = """
SELECT sy2.id, sy2.name
FROM thing_system sy1 INNER JOIN thing_mapdenormalize md1 ON md1.item_id=sy1.id,
 thing_system sy2 INNER JOIN thing_mapdenormalize md2 ON md2.item_id=sy2.id
 WHERE sy1.name='%s'
       AND (SQRT(POW(md1.x-md2.x,2) + POW(md1.y-md2.y,2) + POW(md1.z-md2.z,2))/9460730472580800) <= 6
"""

jumpbridge_usage_fees_fast = """
SELECT j.date,
       COALESCE(IF(ch.name = '*UNKNOWN*', NULL, ch.name), CONCAT('ID: ', j.first_party_id)) AS `char`,
       COALESCE(IF(co.name='*UNKNOWN*', NULL, co.name), CONCAT('ID: ', ch.corporation_id)) as corp,
       a.name as alliance_name,
       FORMAT(j.amount,0) as fee,
       COALESCE(st1.name, CONCAT('ID: ', j.context_id)) as gate_name,
       FORMAT(j.amount/200,0) AS lo_used,
       '' AS rough_mass,
       '' AS possible_ships
FROM thing_esijournal j
    LEFT JOIN thing_character ch on ch.id = j.first_party_id
    LEFT JOIN thing_corporation co ON co.id=ch.corporation_id
    LEFT JOIN thing_alliance a on co.alliance_id=a.id
    LEFT JOIN thing_station st1 on st1.id=j.context_id
WHERE ref_type='structure_gate_jump' AND j.amount >= %s
ORDER BY date DESC
"""

jumpgate_create_statement = """
CREATE OR REPLACE VIEW thing_jumpgates AS SELECT s.id AS id,
       s.system_id AS system_id,
       s.name AS name,
       es.id AS destination_structure_id,
       end.id AS destination_system_id,
       35841 AS type_id,
       NULL AS x,
       NULL AS y,
       NULL AS z
from thing_station s 
    INNER join thing_system end on substr(s.name,(locate(CONCAT(' ', CHAR(187 using ucs2), ' '),s.name) + 3),((locate(' - ',s.name) - locate(CONCAT(' ', CHAR(187 using ucs2), ' '),s.name)) - 3)) = end.name
    join thing_system start on start.id = s.system_id

    inner join thing_station es on es.system_id = end.id
                                  and es.deleted = 0 
                                  and es.type_id = 35841
    inner join thing_corporation ec on es.corporation_id=ec.id
    inner join thing_alliance ea on ec.alliance_id=ea.id
    inner join thing_corporation sc on s.corporation_id=sc.id
    inner join thing_alliance sa on sc.alliance_id=sa.id
where 
    s.type_id = 35841 
    and s.deleted = 0
    and s.corporation_id is not null
    and sa.jb_approved=1 and ea.jb_approved=1 and sc.jb_ignore=0 and ec.jb_ignore=0
order by s.name;
"""
