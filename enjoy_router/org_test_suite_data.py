"""The organization test suite: real organizations in Colorado (and Nocti in Michigan), researched 2026-10-14 from public web
pages (see claude/org-test-suite-research.md in the Project for sources and doubts). Every record carries MARKER so it can be
found and removed. Facts that could not be confirmed say so in the record's notes. Nothing here is a person.

build() returns a plan for bulk_load.load().
"""
MARKER = "LAUNCH test data"


def _note(*parts):
    return ". ".join([MARKER] + [p for p in parts if p])


def _org(key, name, kinds, *notes, **kw):
    return {"key": key, "data": {"name": name, "kinds": kinds, "notes": _note(*notes), **kw}}


def _addr(number, street, city, zip_code, unit=None, state="CO"):
    a = {"street_number": number, "street": street, "locality": city, "region": state, "postal_code": zip_code, "country": "US"}
    if unit:
        a["unit"] = unit
    return a


def _place(key, name, address=None, part_of=None, description="", kind="site"):
    data = {"name": name, "kind": kind, "description": (MARKER + (". " + description if description else ""))}
    if address:
        data["addresses"] = [{"usage": "civic", "is_primary": True, **address}]
    return {"key": key, "data": data, **({"part_of": part_of} if part_of else {})}


def _venue(key, name, slug, *notes, place=None, address=None, activate=True, **kw):
    return {"key": key, "data": {"name": name, "slug": slug, "is_public_venue": False, "status": "inactive",
                                 "notes": _note(*notes), **kw},
            "place": place, "address": address, "activate": activate}


# ---------------------------------------------------------------- BVSD (names from the Colorado Department of Education list)
BVSD_SCHOOLS = [
    "Alicia Sanchez International School", "Angevine Middle School", "Arapahoe Ridge High School", "Aspen Creek K-8 School",
    "Bear Creek Elementary School", "Birch Elementary School", "Boulder Community School/Integrated Studies", "Boulder High School",
    "Boulder Prep Charter High School", "Boulder Universal", "Broomfield Heights Middle School", "Broomfield High School",
    "Casey Middle School", "Centaurus High School", "Centennial Middle School", "Coal Creek Elementary School",
    "Columbine Elementary School", "Community Montessori School", "Creekside Elementary School at Martin Park",
    "Crest View Elementary School", "Douglass Elementary School", "Eisenhower Elementary School", "Eldorado K-8 School",
    "Emerald Elementary School", "Fairview High School", "Fireside Elementary School", "Flatirons Elementary School",
    "Foothill Elementary School", "Gold Hill Elementary School", "Heatherwood Elementary School", "High Peaks Elementary School",
    "Horizons K-8 School", "Jamestown Elementary School", "Justice High Charter School", "Kohl Elementary School",
    "Lafayette Elementary School", "Louisville Elementary School", "Louisville Middle School",
    "Manhattan Middle School of the Arts and Academics", "Meadowlark School", "Mesa Elementary School", "Monarch High School",
    "Monarch K-8 School", "Nederland Elementary School", "Nederland Middle-Senior High School", "Nevin Platt Middle School",
    "New Vista High School", "Peak to Peak Charter School", "Pioneer Bilingual Elementary School", "Ryan Elementary School",
    "Southern Hills Middle School", "Summit Middle Charter School", "Superior Elementary School",
    "University Hill Elementary School", "Whittier Elementary School",
]

# Schools in the city of Boulder: addresses from schooldigger.com (third party, check before relying on them).
# (number, street, unit) ; every one is in Boulder, CO.
BOULDER_SCHOOL_ADDRESSES = {
    "Bear Creek Elementary School": ("2500", "Table Mesa Drive", None),
    "Columbine Elementary School": ("3130", "Repplier Drive", None),
    "Crest View Elementary School": ("1897", "Sumac Avenue", None),
    "Douglass Elementary School": ("840", "75th Street", None),
    "Eisenhower Elementary School": ("1220", "Eisenhower Drive", None),
    "Flatirons Elementary School": ("1150", "7th Street", None),
    "Foothill Elementary School": ("1001", "Hawthorne Avenue", None),
    "Gold Hill Elementary School": ("890", "Main Street", None),     # mountain town with a Boulder mailing address
    "Heatherwood Elementary School": ("7750", "Concord Drive", None),
    "Creekside Elementary School at Martin Park": ("3740", "Martin Drive", None),
    "Mesa Elementary School": ("1575", "Lehigh Street", None),
    "University Hill Elementary School": ("956", "16th Street", None),
    "Whittier Elementary School": ("2008", "Pine Street", None),
    "Community Montessori School": ("805", "Gillaspie Drive", None),
    "High Peaks Elementary School": ("3995", "East Aurora Avenue", None),
    "Boulder Community School/Integrated Studies": ("3995", "East Aurora Avenue", None),   # same building as High Peaks
    "Horizons K-8 School": ("4545", "Sioux Drive", None),
    "Manhattan Middle School of the Arts and Academics": ("290", "Manhattan Drive", None),
    "Casey Middle School": ("1301", "High Street", None),
    "Centennial Middle School": ("2205", "Norwood Avenue", None),
    "Nevin Platt Middle School": ("6096", "Baseline Road", None),
    "Southern Hills Middle School": ("1500", "Knox Drive", None),
    "Summit Middle Charter School": ("4655", "Hanover Avenue", None),
    "Boulder High School": ("1604", "Arapahoe Avenue", None),
    "Fairview High School": ("1515", "Greenbriar Boulevard", None),
    "New Vista High School": ("700", "20th Street", None),
    "Arapahoe Ridge High School": ("6600", "Arapahoe Avenue", None),
    "Boulder Prep Charter High School": ("5075", "Chaparral Court", "1"),
}
SHARED_CAMPUS = ("High Peaks Elementary School", "Boulder Community School/Integrated Studies")

# ---------------------------------------------------------------- St. Vrain (names only; from Wikipedia, secondary and K-8 schools)
SVVSD_SCHOOLS = [
    "Altona Middle School", "Coal Ridge Middle School", "Erie Middle School", "Longs Peak Middle School",
    "Lyons Middle/Senior High School", "Mead Middle School", "Sunset Middle School", "Trail Ridge Middle School",
    "Westview Middle School", "Thunder Valley K-8", "Timberline PK-8", "Soaring Heights PK-8", "Erie High School",
    "Frederick High School", "Longmont High School", "Mead High School", "Niwot High School", "Silver Creek High School",
    "Skyline High School", "New Meridian High School",
]


def _slug(text):
    out = "".join(c.lower() if c.isalnum() else "_" for c in text)
    return "_".join(x for x in out.split("_") if x)


def build():
    orgs, places, venues, links = [], [], [], []

    # ------------------------------------------------------------ BVSD
    orgs.append(_org("bvsd", "Boulder Valley School District", ["school_district"],
                     "Legal designation Boulder Valley School District No. RE-2. bvsd.org says 56 schools in 11 communities; the state list has 55 (this load uses the state list)",
                     legal_name="Boulder Valley School District No. RE-2", short_name="BVSD", aliases=["BVSD", "Boulder Valley Schools"],
                     website_url="https://www.bvsd.org", founded_date="1960",
                     description="Public school district in Boulder County, Colorado."))
    orgs.append(_org("bvsd_board", "Boulder Valley School District Board of Education", ["governing_body"],
                     "Seven members, each representing one of seven districts in the BVSD area", short_name="BVSD Board of Education"))
    links.append(("o:bvsd_board", "part_of", "o:bvsd", {"description": "The elected board that governs the district."}))
    places.append(_place("bvsd_hq", "BVSD Education Center", _addr("6500", "Arapahoe Road", "Boulder", "80303"),
                         description="BVSD headquarters"))
    links.append(("o:bvsd", "operates_at", "p:bvsd_hq", {"is_primary": True, "description": "Headquarters"}))
    shared_done = False
    for name in BVSD_SCHOOLS:
        key = "bvsd_" + _slug(name)
        orgs.append(_org(key, name, ["school"], "School in the Boulder Valley School District (state list name)"))
        links.append(("o:" + key, "part_of", "o:bvsd", {}))
        addr = BOULDER_SCHOOL_ADDRESSES.get(name)
        if not addr:
            continue
        number, street, unit = addr
        if name in SHARED_CAMPUS:
            if not shared_done:
                places.append(_place("bvsd_aurora_campus", "3995 E Aurora Ave (High Peaks and Boulder Community School of Integrated Studies)",
                                     _addr(number, street, "Boulder", None, unit),
                                     description="One building, two BVSD schools. Address from schooldigger.com"))
                shared_done = True
            place_key = "bvsd_aurora_campus"
        else:
            place_key = "bvsd_place_" + _slug(name)
            note = "Address from schooldigger.com (third party)"
            if name.startswith("Gold Hill"):
                note += "; Gold Hill is a mountain town with a Boulder mailing address, so it may not count as the city of Boulder"
            places.append(_place(place_key, name, _addr(number, street, "Boulder", None, unit), description=note))
        links.append(("o:" + key, "operates_at", "p:" + place_key, {"is_primary": True}))
    # postal codes were not sourced for schools; remove the empty key
    for p in places:
        for a in p["data"].get("addresses", []):
            if a.get("postal_code") is None:
                a.pop("postal_code", None)

    # ------------------------------------------------------------ St. Vrain
    orgs.append(_org("svvsd", "St. Vrain Valley Schools", ["school_district"],
                     "Legal designation St. Vrain Valley School District No. Re1J. Organized 1961. School list is secondary and K-8 schools only (Wikipedia); elementary schools are not loaded",
                     legal_name="St. Vrain Valley School District No. Re1J", short_name="SVVSD",
                     aliases=["St. Vrain Valley School District", "SVVSD"], website_url="https://www.svvsd.org", founded_date="1961",
                     description="Public school district serving northern Boulder County and parts of Larimer and Weld counties, Colorado."))
    orgs.append(_org("svvsd_board", "St. Vrain Valley Schools Board of Education", ["governing_body"], "Seven members"))
    links.append(("o:svvsd_board", "part_of", "o:svvsd", {"description": "The elected board that governs the district."}))
    places.append(_place("svvsd_hq", "St. Vrain Valley Schools headquarters", _addr("395", "South Pratt Parkway", "Longmont", "80501"),
                         description="St. Vrain Valley Schools headquarters"))
    links.append(("o:svvsd", "operates_at", "p:svvsd_hq", {"is_primary": True, "description": "Headquarters"}))
    for name in SVVSD_SCHOOLS:
        key = "svvsd_" + _slug(name)
        orgs.append(_org(key, name, ["school"], "School in St. Vrain Valley Schools. No address loaded"))
        links.append(("o:" + key, "part_of", "o:svvsd", {}))

    # ------------------------------------------------------------ Ozo
    orgs.append(_org("ozo", "OZO Coffee Company", ["business"], "Founder and CEO Justin Hartman (Daily Coffee News, 2015). Todd's earlier story was four shops plus a factory; ozocoffee.com now lists five cafes",
                     short_name="OZO", aliases=["Ozo Coffee", "Ozo's", "OZO Coffee Roasters"], website_url="https://ozocoffee.com", founded_date="2007",
                     description="Boulder coffee roaster and cafes."))
    places.append(_place("ozo_roastery", "OZO Roastery and Lab", _addr("1898", "South Flatiron Court", "Boulder", "80301", "#110"),
                         description="Roasting and wholesale (Roastery + Lab is wholesale only). The Roastery Cafe is a venue at this same address"))
    links.append(("o:ozo", "operates_at", "p:ozo_roastery", {"is_primary": True, "description": "Roastery and wholesale lab"}))
    venues.append(_venue("ozo_roastery_cafe", "OZO Roastery Cafe", "ozo_roastery_cafe", "Cafe at the roastery address. Test venue, not public",
                         place="ozo_roastery", website_url="https://ozocoffee.com"))
    for key, nm, number, street, city, zip_code, unit in [
        ("ozo_arapahoe", "OZO Coffee Arapahoe", "5340", "Arapahoe Avenue", "Boulder", "80303", None),
        ("ozo_west_pearl", "OZO Coffee West Pearl", "1015", "Pearl Street", "Boulder", "80302", None),
        ("ozo_east_pearl", "OZO Coffee East Pearl", "1521", "Pearl Street", "Boulder", "80302", None),
        ("ozo_longmont", "OZO Coffee Longmont", "1232A", "South Hover Street", "Longmont", "80501", "#400"),
    ]:
        venues.append(_venue(key, nm, key, "Cafe. Test venue, not public", address=_addr(number, street, city, zip_code, unit),
                             website_url="https://ozocoffee.com"))
    for k in ("ozo_roastery_cafe", "ozo_arapahoe", "ozo_west_pearl", "ozo_east_pearl", "ozo_longmont"):
        links.append(("v:" + k, "operated_by", "o:ozo", {}))

    # ------------------------------------------------------------ Amante
    orgs.append(_org("amante", "Amante Coffee", ["business"], "Owner Jordan Karp since 2009 (Westword); original founder not found. Craft.co lists the headquarters as 1612 17th St, Denver (the LoDo cafe)",
                     website_url="https://www.amantecoffee.com", aliases=["Amante Coffee Roasters"],
                     description="Coffee roaster and cafes in Boulder and Denver."))
    for key, nm, number, street, city, zip_code, unit, state_note, act in [
        ("amante_downtown", "Amante Coffee Downtown", "1023", "Walnut Street", "Boulder", "80302", None, "MapQuest says 1035 Walnut; Amante's own page says 1023", True),
        ("amante_uptown", "Amante Coffee Uptown", "4580", "Broadway", "Boulder", "80304", None, "", True),
        ("amante_lodo", "Amante Coffee LoDo", "1612", "17th Street", "Denver", "80202", None, "", True),
        ("amante_baseline", "Amante Coffee Baseline", "2850", "Baseline Road", "Boulder", "80303", "A-4", "Permanently closed according to Amante's own page; closing date unknown", False),
    ]:
        venues.append(_venue(key, nm, key, "Cafe. Test venue, not public", state_note, address=_addr(number, street, city, zip_code, unit), activate=act))
        links.append(("v:" + key, "operated_by", "o:amante", {}))

    # ------------------------------------------------------------ CU and Laughing Goat
    orgs.append(_org("cu_system", "University of Colorado", ["college_university"], "System; founded 1876; president Todd Saliman per Wikipedia",
                     short_name="CU", website_url="https://www.cu.edu", founded_date="1876"))
    orgs.append(_org("cu_boulder", "University of Colorado Boulder", ["college_university"], "Flagship campus of the CU system; street address not found",
                     short_name="CU Boulder", aliases=["CU", "Colorado University Boulder"], founded_date="1876"))
    orgs.append(_org("cu_regents", "Regents of the University of Colorado", ["governing_body"], "Nine elected members"))
    links.append(("o:cu_boulder", "part_of", "o:cu_system", {}))
    links.append(("o:cu_regents", "part_of", "o:cu_system", {"description": "The elected board that governs the CU system."}))
    places.append(_place("cu_boulder_campus", "CU Boulder campus", description="No address loaded; a place with a name only", kind="site"))
    places.append(_place("norlin_library", "Norlin Library", part_of="cu_boulder_campus",
                         description="No street address found. Inside the CU Boulder campus place; the Laughing Goat cafe is in its Learning Commons"))
    links.append(("o:cu_boulder", "operates_at", "p:cu_boulder_campus", {"is_primary": True, "description": "Campus"}))
    orgs.append(_org("goat", "The Laughing Goat", ["business"], "Owner John Jenkins per a 2020 CU Libraries article. Boulder Magazine lists 1709 Pearl St and 1720 Pleasant St; the Pleasant St address is unexplained and is not loaded",
                     aliases=["Laughing Goat Coffeehouse", "Laughing Goat"], website_url="https://thelaughinggoat.com",
                     description="Boulder coffeehouse with a second shop inside CU Boulder's Norlin Library."))
    venues.append(_venue("goat_pearl", "The Laughing Goat (Pearl Street)", "goat_pearl", "Coffeehouse. Test venue, not public",
                         address=_addr("1709", "Pearl Street", "Boulder", "80302")))
    venues.append(_venue("goat_norlin", "The Laughing Goat (Norlin Commons)", "goat_norlin",
                         "Cafe inside CU's Norlin Library since the 2008 renovation. Who runs it is not stated on CU's page; the Goat's site and a CU Libraries article say it is theirs. The place has no address, so the venue stays inactive",
                         place="norlin_library", activate=False))
    links.append(("v:goat_pearl", "operated_by", "o:goat", {}))
    links.append(("v:goat_norlin", "operated_by", "o:goat", {"valid_from": "2008"}))
    links.append(("v:goat_norlin", "part_of", "o:cu_boulder", {"description": "Located on the CU Boulder campus, in Norlin Library"}))

    # ------------------------------------------------------------ Panera
    orgs.append(_org("panera", "Panera Bread Company", ["business"], "Headquarters Fenton, Missouri (street address not found). St. Louis Bread Co founded 1987 in Kirkwood MO by Ken and Linda Rosenthal; Au Bon Pain bought it in 1993; renamed Panera in 1997",
                     aliases=["Panera Bread", "Panera", "Saint Louis Bread Co."], founded_date="1987",
                     description="Bakery-cafe chain; most Colorado cafes are run by franchisees."))
    orgs.append(_org("panera_brands", "Panera Brands", ["business"], "Formed 2021-08-25 when Panera merged with Caribou Coffee and Einstein Bros. Bagels", founded_date="2021-08"))
    orgs.append(_org("jab", "JAB Holding Company", ["business"], "Owned by the Reimann family of Germany (Wikipedia). Bought Panera 2017-07-11 for $7.5 billion"))
    orgs.append(_org("breads_world", "Breads of the World, LLC", ["business"],
                     "Panera franchisee in Colorado: 37 cafes in 2016 (Denver Post Top Workplaces). Its Colorado cafes were bought by Manna Development Group in May 2018. Whether the company still exists is not known",
                     status="inactive"))
    orgs.append(_org("manna", "Manna Development Group", ["business"],
                     "Panera franchisee; founded 2003; bought 38 Colorado cafes in May 2018 and then ran 130 cafes in seven states. WHO RUNS PANERA IN COLORADO TODAY IS NOT CONFIRMED (last confirmed 2018)",
                     founded_date="2003"))
    links.append(("o:panera", "part_of", "o:panera_brands", {"valid_from": "2021-08"}))
    links.append(("o:panera", "affiliated_with", "o:jab", {"valid_from": "2017-07", "description": "JAB Holding bought Panera in July 2017"}))
    links.append(("o:breads_world", "affiliated_with", "o:panera", {"valid_to": "2018-05", "description": "Franchisee in Colorado"}))
    links.append(("o:breads_world", "succeeded_by", "o:manna", {"valid_from": "2018-05", "description": "Manna bought 38 Colorado cafes"}))
    links.append(("o:manna", "affiliated_with", "o:panera", {"description": "Franchisee"}))
    for key, nm, number, street, city, zip_code in [
        ("panera_boulder_29th", "Panera Bread, 29th Street (#3083)", "1855", "29th Street", "Boulder", "80301"),
        ("panera_longmont_ken_pratt", "Panera Bread, Ken Pratt Boulevard (#3078)", "425", "Ken Pratt Boulevard", "Longmont", "80501"),
    ]:
        venues.append(_venue(key, nm, key, "Address from city-data.com (third party, may be stale). Operator not confirmed", address=_addr(number, street, city, zip_code)))
        links.append(("v:" + key, "operated_by", "o:manna", {"valid_from": "2018-05", "description": "Operator not confirmed; last confirmed owner of Colorado cafes"}))

    # ------------------------------------------------------------ extras
    orgs.append(_org("rmaiig", "Rocky Mountain AI Interest Group", ["community_group"],
                     "Meetup group based in Boulder with about 4,700 members; no fixed place (has met at CU's ATLAS). Organizer names not loaded",
                     short_name="RMAIIG", aliases=["RMAIIG", "Rocky Mountain Artificial Intelligence Interest Group"],
                     website_url="https://www.meetup.com/rocky-mountain-artificial-intelligence-interest-group-rmaiig/",
                     description="Community of technical and non-technical people interested in generative AI."))
    orgs.append(_org("nocti", "NOCTI", ["nonprofit", "association"], "Outside Colorado on purpose (Todd chose the Michigan address). Board of Trustees; non-profit consortium of all fifty states and territories",
                     legal_name="National Occupational Competency Testing Institute", short_name="NOCTI", aliases=["Nocti", "National Occupational Competency Testing Institute"],
                     website_url="https://www.nocti.org", founded_date="1969",
                     description="Builds competency assessments and credentials for career and technical education."))
    places.append(_place("nocti_hq", "NOCTI headquarters", _addr("500", "North Bronson Avenue", "Big Rapids", "49307", state="MI"), description="NOCTI headquarters"))
    links.append(("o:nocti", "operates_at", "p:nocti_hq", {"is_primary": True, "description": "Headquarters"}))

    return {"marker": MARKER, "orgs": orgs, "places": places, "venues": venues, "links": links}
