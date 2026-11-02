# Research notes: how a US craft whiskey distillery starts up and operates

Gathered Nov 2, 2026. Numbers are the "real-ish" defaults Barrel uses; each line says where it lives in the sim (`params.py` unless noted).

## Permits and compliance
| Fact | Barrel default | Source |
|---|---|---|
| TTB original DSP permit: median 44–48 calendar days (Jul–Sep 2026); goal 85% within 75 days. Includes field investigation and premises review. | DSP processing lognormal, median 47 d, p85 ≈ 75 d; requires a signed lease + described equipment | [TTB permit processing times](https://www.ttb.gov/nrc/statistics-original-applications-to-operate) |
| No federal fee to apply. | $0 federal, state license fee $3–6k | [TTB DS permits](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/permits) |
| Bond (TTB F 5110.56) required for a beverage DSP once spirits tax liability exceeds $50,000/yr, or if not paying on a deferred basis. | Bond needed once projected or prior-year tax > $50k; premium ~2% of penal sum | [TTB DSP docs](https://www.ttb.gov/online-services/permits/permits-rd/distilled-spirits-plant), [27 CFR 19 Subpart F](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-19/subpart-F/subject-group-ECFR51c3c6cb70df452) |
| COLA label approval: median 6 calendar days for spirits (Nov 2026), goal 85% within 15 days. | COLA lognormal, median 6 d | [TTB label processing times](https://www.ttb.gov/regulated-commodities/labeling/processing-times) |
| Monthly operations reports (5110.40 production, 5110.11 storage, 5110.28 processing) due the 15th of the following month, even with zero activity. | `file_operations_report` monthly, due day 15; late → warning, then penalties and inspection risk | [TTB due dates](https://www.ttb.gov/taxes/tax-audit/due-dates-for-operational-reports), [27 CFR 19.632](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-19/subpart-V/subject-group-ECFR58ebdf5abdbeb0b/section-19.632) |
| Excise returns quarterly if ≤ $50k liability this and last year, due 14 days after quarter end; otherwise more frequent. | Quarterly ≤ $50k, else monthly (simplified from semi-monthly), due +14 d | [TTB newsletter Oct 2026](https://content.govdelivery.com/accounts/USTTB/bulletins/42e9bb7), [27 CFR 19.235](https://codes.findlaw.com/cfr/title-27-alcohol-tobacco-products-and-firearms/cfr-sect-27-19-235/) |
| FET: $13.50/PG general; CBMA reduced $2.70/PG on first 100,000 PG per calendar year, $13.34 next 22.13M PG — only for spirits the DSP distilled or processed (not just bottled) since 2022. | Tiered per calendar year; sourced whiskey that is only bottled pays $13.50 | [TTB tax rates](https://www.ttb.gov/taxes/tax-audit/taxes-and-filing/tax-rates), [26 USC 5001](https://uscode.house.gov/us/usc/119-136/t26/s5001/), [TTB CBMA](https://www.ttb.gov/regulated-commodities/beverage-alcohol/cbma/craft-beverage-modernization-and-tax-reform-cbmtra) |
| Excise is paid at removal from bond, not at barreling. | Tax accrues when bottled goods leave bond (shipped or moved to the tasting room) | [Union Metric SBA feasibility](https://unionmetricfeasibility.com/engagements/brewery-distillery-feasibility-study-craft-distillery-sba-7a) |

## Standards of identity and labels
| Fact | Barrel rule | Source |
|---|---|---|
| Straight bourbon: ≥51% corn, ≤160 proof off still, ≤125 proof into new charred oak, ≥2 years, no additives. | `straight_bourbon` label needs every barrel ≥2.0 y, new charred oak, entry ≤125 | [27 CFR 5.143](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5/subpart-I/section-5.143) |
| Whisky under 4 years must carry an age statement. | A whiskey label with no age statement on spirit <4 y is label fraud | [27 CFR 5.74](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5/subpart-E/section-5.74) |
| Bottled in bond: one distiller, one distillery, one distilling season, ≥4 y, exactly 100 proof. | `bottled_in_bond` checks all four | [27 CFR 5.88](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5/subpart-F/section-5.88) |
| Age statement = youngest spirit in the bottle. | Age claim vs. youngest barrel's true age | [TTB BAM ch. 8](https://www.ttb.gov/system/files/images/pdfs/spirits_bam/chapter8.pdf) |

## Production economics
| Fact | Barrel default | Source |
|---|---|---|
| ~5 proof gallons per bushel for large distillers. | 4.3–5.0 PG/bu depending on still and distiller skill | [Whisky Advocate](https://whiskyadvocate.com/why-bourbon-prices-got-higher) |
| 53-gal barrel at 125 proof = 66.3 PG; ~10% loss year 1, ~4%/yr after. | Entry proof chosen 100–125; angel's share 9–11% y1 then ~4%/yr, scaled by temperature/humidity and rick floor | [Distiller Magazine](https://distilling.com/distillermagazine/the-long-haul/), [Distillery Trail](https://www.distillerytrail.com/blog/what-is-the-angels-share/) |
| Hot top floors mature faster and concentrate proof; cool damp floors lower proof. | Floors low/mid/high with temperature offsets −6/0/+8 °F | [Distillery Trail](https://www.distillerytrail.com/blog/what-is-the-angels-share/) |
| New 53-gal charred oak barrel $348–$625; lead time 3–12 weeks. | $380 × cooperage index; lead time 6–12 wks, shortages add 8+ | [Barrels Direct](https://www.barrelsdirect.com/product/new-53-gallon-200l-american-oak-classic/), [Barrel Mill](https://thebarrelmill.com/product/53-gallon-oak-barrel/) |
| Glass $1–2/bottle, closure $0.35, label ~$1. | Dry goods $3.20/bottle × glass index | [Whisky Advocate](https://whiskyadvocate.com/why-bourbon-prices-got-higher) |
| 250-gal pot still ~$115k; small craft equipment $200k–$1.5M; build-out $50k–$400k. | Three still packages $140k / $320k / $780k | [ADI business plan](https://distilling.com/business-development/down.pdf), [Barrel Clarity](https://barrelclarity.com/blog/distillery-startup-costs-guide-2025/) |
| NGS ~$330 per 55-gal drum of 95%; gin from NGS in two days. | NGS $3.40/PG (190 proof), redistilled gin/vodka qualify for CBMA | [ADI business plan](https://distilling.com/business-development/down.pdf) |
| Vodka/gin first for cash flow while whiskey ages 2–4 y; aging working capital is the main failure point. | Bridge products available from first COLA; seed capital is tight on purpose | [Union Metric](https://unionmetricfeasibility.com/engagements/brewery-distillery-feasibility-study-craft-distillery-sba-7a), [Barrel Clarity](https://barrelclarity.com/blog/distillery-startup-costs-guide-2025/) |

## Market, channels and finance
| Fact | Barrel default | Source |
|---|---|---|
| 2025: 16.1M barrels aging in KY; production cut ~28%; new-fill bulk ~$550/barrel vs ~$950 a few years earlier; craft insolvencies and liquidations. | Demand regime starts "soft" in `realistic`; bulk new-fill index centered ~$600 | [Herald-Leader inventory](https://www.kentucky.com/news/business/article312441104.html), [Herald-Leader bulk](https://www.kentucky.com/news/business/article312418416.html), [Bloomberg Law](https://news.bloomberglaw.com/bankruptcy-law/distilleries-navigate-solvency-issues-following-covid-sales-boom) |
| American whiskey exports −19% in 2025, EU −35%, Canada pulled US spirits (−57% whiskey); 30% EU tariff threat suspended. | Tariff factor: export-channel tariff events and retaliation shelf pulls | [DISCUS 2025 exports](https://distilledspirits.org/wp-content/uploads/2026/03/Final-DISCUS-2025-American-Spirits-Exports-Report-.pdf), [Herald-Leader exports](https://www.kentucky.com/lexgoeat/bourbon/article315249863.html) |
| Control states: the state is the wholesaler; Michigan's state markup 51–65%. | Two control-state boards with listing windows and fixed markups | [NABCA](https://www.nabca.org/sites/default/files/assets/files/control-state/Control_State_Datasets_Overview_SAM2%201%207%202025.pdf), [MCL 436.1233](https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-436-1233) |
| Tasting room is the highest-margin channel; three-tier keeps 30–50% at wholesale; laws vary by state. | Tasting room needs a state retail privilege; distributors take ~30% and retail ~33% | [Crestmont](https://www.crestmontcapital.com/blog/distillery-equipment-loans-still-boiler-and-mash-tun-options), [ADI tasting room survey](https://distilling.com/resources/government-affairs/survey-of-distillery-tasting-room-laws/) |
| Barrel-backed lending: specialist ABL, up to ~65% advance (Live Oak), $1–30M, 45–60 days to fund. | Barrel line 50% of appraised value, 45–60 d, prime+4 | [Whiskey Capital](https://whiskeycapitalfinance.com/), [Live Oak](https://resources.liveoak.bank/hubfs/sales_sheets/whiskey_financing.pdf), [Underridge](https://www.underridge.com/underwriting/whiskey-barrels) |
| SBA 7(a) ~10.5–13.5% APR for 10-year loans in 2026; up to $5M. | SBA 7(a) ≤ $5M, prime+2.75, 10 y amortization, 6–12 wk decision | [Crestmont](https://www.crestmontcapital.com/blog/distillery-equipment-loans-still-boiler-and-mash-tun-options), [SBA](https://www.sba.gov/sba-lenders/) |

## Simplifications (deliberate)
Semi-monthly excise returns are modeled as monthly; one state of operation plus out-of-state distributors; no formula approvals for flavored products; insurance is one package policy; the founder's own salary is not paid.
