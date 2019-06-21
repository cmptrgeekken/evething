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
	) ci ON c.contract_id=ci.contract_id
    INNER JOIN thing_item i ON ci.item_id=i.id
    INNER JOIN
		(
			SELECT 
				sci.contract_id, 
                SUM(sci.quantity*si.sell_fivepct_price) AS contract_value 
			FROM thing_contractitem sci
				INNER JOIN thing_item si ON sci.item_id=si.id
			GROUP BY sci.contract_id
		) sc ON sc.contract_id=ci.contract_id
WHERE c.contract_id IN (SELECT DISTINCT c.contract_id
   FROM thing_contract c
   WHERE c.assignee_id=c.corporation_id
   AND c.type = 'Item Exchange'
   AND c.issuer_corp_id != c.corporation_id
   AND c.status = 'Completed'
   AND EXISTS (SELECT 1 FROM thing_contractitem ci INNER JOIN thing_pricewatch pw ON ci.item_id=pw.item_id WHERE ci.contract_id=c.contract_id AND ci.included=1 AND pw.active=1)
   AND NOT EXISTS (SELECT 1 from thing_contractitem ci WHERE ci.item_id NOT IN (SELECT item_id from thing_pricewatch pw WHERE pw.active=1) AND ci.contract_id=c.contract_id AND ci.included=1)
) and c.price > 0
  AND c.date_accepted > DATE_ADD(NOW(), INTERVAL -1 MONTH)
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
LEFT JOIN thing_itemmaterial im ON im.item_id=outer_group.item_id
LEFT JOIN thing_item imi ON im.material_id=imi.id
WHERE item_name NOT LIKE '%Fuel Block'
GROUP BY outer_group.item_id) material_group
LEFT JOIN thing_itemmaterial im ON im.item_id=material_group.item_id
LEFT JOIN thing_item imi ON im.material_id=imi.id
) final_group
GROUP BY final_group.item_name
