"""
Populate Technology, Fuel, and single marginal_cost for the final generator CSV.

Input:  data read from Google Sheet 1eQt6UqjGjpRrciNag23GkZRJgim7OyiSWO5cDxn6juA
Output: task-pipeline/generator_data_final.csv

Marginal cost approach:
  - Log-linear interpolation/extrapolation over reference anchor points
    (from artifact f62ef837) by Technology × fuel category
  - For dual-fuel plants the PRIMARY fuel (first listed) is used for
    the single marginal_cost column
  - HSD carries a 10 % premium over the HFO "liquid fuel" reference
"""

import io
import numpy as np
import pandas as pd
from pathlib import Path

OUT_CSV = Path("task-pipeline/generator_data_final.csv")

# ---------------------------------------------------------------------------
# RAW DATA  (read directly from Google Drive MCP output)
# ---------------------------------------------------------------------------
RAW = """\
Area,Name,Technology,Fuel,Bus,Present Capacity (MW),Marginal Cost (USD/MWh)
Dhaka,Ghorasal Repowered CCPP Unit-3,CCGT,,GhorashalSouthWest_230kV,260,
,Ghorasal Repowered CCPP Unit-4,CCGT,,GhorashalSouthWest_230kV,240,
,Ghorasal TPP Unit-5,OCGT,,GhorashalSouthWest_230kV,190,
,Ghorasal 365 MW CCPP Unit-7,CCGT,,GhorashalSouthWest_230kV,365,
,Ghorashal 108 MW PP (Regent),ICE,,GhorashalSouthWest_230kV,97.7,
,Haripur GTPP,OCGT,,Haripur_132kV,20,
,Haripur 412 MW CCPP,CCGT,,Haripur_132kV,412,
,Meghnaghat 450 MW CCPP (MPL),CCGT,,Meghnaghat_230kV,450,
,Meghnaghat CCPP(Summit),CCGT,,Meghnaghat_230kV,335,
,Madanganj-55 MW PP(Summit),,,Madanganj_132kV,55,
,Siddhirganj 210 MW TPP,,,Haripur_230kV,115,
,Siddhirganj 2*120 MW GTPP,,,Siddhirganj_132kV,210,
,Siddhirganj 335 MW CCPP,CCGT,,Siddhirganj_230kV,335,
,Gagnagar 102 MW PP (Digital Power),,,Sitalakhya_132kV,102,
,Kamalaghat 54 MW PP(Banco Energy),,,Munshiganj_132kV,53.97,
,Kodda 150 MW PP BRPL,,,Kodda_132kV,149.36,
,Manikganj 55 MW PP (Northern),,,Savar_132kV,55,
,Nababganj 55 MW PP (Southern power ),,,Hasnabad_132kV,55,
,Summit Power Ashulia,,,Savar_132kV,33.75,
,Summit Power Madhabdi,,,Narsingdi_132kV,23,
,Gazipur 52 MW PP,,,Kodda_132kV,52.194,
,Tongi 80 MW GTPP,,,Tongi_132kV,105,
,Kodda 300 MW PP Unit-2 (Summit),,,Tongi_230kV,300,
,Kodda 149 MW PP Unit-1 (Summit),,,Kodda_132kV,149,
,Gazipur 100 MW PP,,,Kodda_132kV,105,
,Meghnaghat 104 MW PP (OPCL),,,Sonargaon_132kV,104,
,Manikgonj 162MW PP(MPGL),,,Manikganj_132kV,162,
,Spectra Solar Plant Ltd.,,,Manikganj_132kV,35,
,Kanchan Purbachal Power Generation Ltd.,,,Purbachal_132kV,55,
,Unique Meghnaghat Power Limited (UMPL),,,Meghnaghat_400kV,584,
,Meghnaghat CCPP(Summit)-2,CCGT,,Meghnaghat_400kV,583,
,JERA Meghnaghat Power Limited,,,Meghnaghat_400kV,718,
,Sreepur 150 MW PP BRPL,,,BarmiPP_132kV,160,
Chattogram,Chattogram TPP,,,Raozan_230kV,360,
,Raozan 25 MW PP,,,Raozan_230kV,25.5,
,Teknaf  20MW PP (Solartech),,,Cox'sBazar_132kV,20,
,Patenga 50MW PP (Baraka),,,Halishahar_132kV,50,
,"Karnaphuli Hydro PP Unit-1,2,3,4, 5",,,Kaptai_132kV,230,
,Sikalbaha 225MW CCPP,,,Sikalbaha_230kV,225,
,Sikalbaha Peaking GT,,,Sikalbaha_132kV,150,
,Sikalbaha 105 MW PP (Baraka Sikalbaha),,,Sikalbaha_230kV,105,
,Hathazari 100 MW peaking PP,,,Hathazari_132kV,98,
,Dohazari -Kalaish 100 MW Peaking,,,Dohazari_132kV,102,
,Juldah 100 MW PP Unit-3 (Acorn),,,Juldah_132kV,100,
,"Malancha, Ctg. EPZ (United)",,,Halishahar_132kV,42,
,Chattogram 108 MW PP (ECPV),,,Sikalbaha_132kV,108,
,Kaptai 7 MW  Solar PP,,,Kaptai_132kV,6,
,Anwara 300 MW PP (United),,,Anwara_230kV,300,
,Zodiac Power,,,Sikalbaha_230kV,54.363,
,Karnaphuli Power Ltd.,,,Sikalbaha_230kV,110,
,Juldah unit-2 (Acorn),,,Juldah_132kV,100,
,Anlima Energy Ltd.,,,Sikalbaha_230kV,116,
,Mirsharai 150 MW BRPL,,,Mirsarai_230kV,163,
,SS Power,,,Banskhali_400kV,1224,
,Cox's Bazar Wind,,,USDKWindFarm_132kV,60,
,Matarbari 2*600 MW (CPGCBL),,,Matarbari_400kV,1150,
Cumilla,Ashuganj CCPP 225 MW,CCGT,,Ashuganj_132kV,221,
,Ashuganj 450 MW CCPP(North),CCGT,,AshuganjNorth_400kV,350.01,
,Ashuganj 450 MW CCPP(South),CCGT,,Ashuganj_230kV,342.01,
,Ashuganj 420 MW CCPP(East),CCGT,,Ashuganj_230kV,393,
,Ashuganj TSK 50 MW PP,,,Ashuganj_132kV,46.701,
,Ashuganj 55 MW PP (Precision),,,Ashuganj_132kV,52.824,
,Ashuganj 195 MW PP (APSCL-United),,,Ashuganj_230kV,195,
,Ashuganj 51 MW PP (Midland),,,Ashuganj_230kV,51,
,Ashuganj 150MW PP (Midland),,,Ashuganj_230kV,150,
,Titas 50 MW Peaking PP,,,DaudkandiPP_132kV,52,
,Chandpur 150 MW CCPP,,,Chandpur_132kV,163,
,Chandpur 200MW (Desh energy),,,DeshPP_132kV,200,
,Jangalia 52 MW PP (Lakdanavi),,,CumillaSouth_132kV,52.2,
,Cumilla 25 MW PP (Summit),,,CumillaNorth_132kV,25,
,Feni Lanka Power,,,Feni_132kV,114,
,Chowmuhani 113 MW,,,Chowmuhani_132kV,113,
,Chandpur 115(Doreen),,,Chandpur_132kV,115,
,Sonagazi 75 MW (AC) Solar Power Plant,,,Sonagazi_230kV,75,
Mymensingh,RPCL 210MW CCPP,CCGT,,RPCLPP_132kV,210,
,Sarishabari 3 MW Solar Plant,,,Jamalpur_132kV,2.71,
,Mymensingh 200 MW PP (United),,,UnitedPP_132kV,200,
,Jamalpur 115 MW PP (United),,,UnitedPP_132kV,115,
,Sutiakhali 50 MW Solar PP,,,Mymensingh_132kV,50,
,Tangail Palli Power Gen 22 MW,,,Tangail_132kV,22,
,Bhairab 54.5 MW,,,Kishoreganj_132kV,54.5,
Sylhet,Moulvibazar 10 MW Solar Power Plant,,,Srimangal_132kV,0,
,Fenchugonj CCPP Phase-1,CCGT,,Fenchuganj_132kV,90,
,Fenchugonj CCPP Phase-2,CCGT,,Fenchuganj_132kV,90,
,Kushiara 163 MW CCPP (KP),CCGT,,Fenchuganj_230kV,163,
,Shajibazar 330 MW CCPP,CCGT,,Shahjibazar_230kV,330,
,Shahjibazar GTPP Unit- 8 & 9,,,Shahjibazar_132kV,66,
,Shahjibazar 86MW PP (Shahjibazar),,,Shahjibazar_132kV,86,
,Shahjibazar 100 MW GTPP,,,Shahjibazar_132kV,100,
,Sylhet 225 MW CCPP,CCGT,,Sylhet_132kV,231,
,Sylhet  20 MW GTPP,,,Sylhet_132kV,20,
,Shahjahanulla 25 MW PP,,,Sylhet_132kV,25,
,Bibiana-II 341 MW CCPP (Summit),CCGT,,Bibiyana_400kV,341,
,Bibiyana-III 400 MW CCPP,CCGT,,Bibiyana_400kV,400,
,Bibiyana South 400 MW,,,Bibiyana_400kV,383,
Khulna,Bheramara GTPP Unit-3,,,Bheramara_132kV,16,
,Faridpur 50 MW Peaking PP,,,Faridpur_132kV,54,
,Khulna 225 MW CCPP,CCGT,,KhulnaCentral_132kV,230,
,Gopalganj 100 MW Peaking PP,,,Gopalganj_132kV,109,
,Bheramara 410 MW CCPP,CCGT,,Bheramara_132kV,410,
,Rupsha 105 MW PP (Orion rupsha),,,LabancharaPP_132kV,105,
,Madhumati 100 MW PP,,,Gopalganj_132kV,105,
,Mongla Orion 100 MW Solar PP,,,Mongla_132kV,100,
,Khulna 330 MW CCPP,CCGT,,Goalpara_132kV,336,
,Rampal 1320 MW (BIFPCL),,,Rampal_400kV,1234.2,
Barishal,Patuakhali 1320 MW (RNPL),,,RNPL_400kV,1244,
,Barisal 110 MW PP (Summit ),,,Barishal_132kV,110,
,Bhola  33 MW PP (Venture),,,Borhanuddin_230kV,11.04,
,Bhola 225 MW  CCPP,,,Borhanuddin_230kV,194,
,Payra 1320 MW,,,PayraPP_400kV,1244,
,Bhola Nutan Biddut BD LTD,,,Borhanuddin_230kV,220,
,United Payra Power Ltd.,,,Patuakhali_132kV,150,
,Barisal 307 MW,,,Barishal307MWPP_400kV,307,
,Barisal 1 MW Solar Plant,,,Barishal_132kV,1,
Rajshahi,Pabna 64 MW Solar Plant,,,Pabna64MWSolarPP_132kV,64.55,
,Baghabari 71 MW GTPP,,,Baghabari_132kV,70,
,Baghabari  100 MW GTPP,,,Baghabari_132kV,100,
,Baghabari  50 MW Peaking PP,,,Baghabari_132kV,52,
,Bera 70 MW Peaking PP,,,BeraPP_132kV,71,
,Katakhali 50 MW Peaking PP,,,Rajshahi_132kV,50,
,Sirajganj 225MW CCPP Unit-1,CCGT,,SirajganjSouthWest_230kV,214,
,Sirajganj 225MW CCPP Unit-2,CCGT,,SirajganjSouthWest_230kV,220,
,Sirajganj 225MW CCPP Unit-3,CCGT,,SirajganjSouthWest_230kV,220,
,Sirajganj 400 MW CCPP Unit-4,CCGT,,SirajganjSouthWest_230kV,413.792,
,Santahar  50 MW Peaking PP,,,Naogaon_132kV,50,
,Natore 52 MW PP (Rajlanka),,,Natore_132kV,52.2,
,Chapainawabganj 100 MW Peaking PP,,,Amnura_132kV,104,
,Bagura 113 MW PP (Confidence)-2,,,BoguraSouth_132kV,113,
,Bagura 113 MW PP (Confidence)-1,,,BoguraSouth_132kV,113,
,Sirajganj 6.55 MW Solar,,,Sirajganj_132kV,6.09,
,Sirajganj 68 MW Solar Park,,,Sirajganj_132kV,68,
,Pabna Solar 100 MW,,,DynamicSunSolarPP_132kV,100,
,Sirajganj 2 MW Wind Power Plant,,,Sirajganj_132kV,2,
Rangpur,Saidpur 150 MW Simple Cycle Power Plant,,,Saidpur_132kV,162.443,
,Barapukuria TPP Unit-1 & 2,,,Barapukuria_230kV,170,
,Barapukuria 275 MW TPP Unit-3,,,Barapukuria_230kV,274,
,Rangpur 20 MW  GTPP,,,Rangpur_132kV,20,
,Saidpur 20 MW GTPP,,,Saidpur_132kV,20,
,Rangpur 113 MW PP (Confidence),,,ConfidencePP_132kV,113,
,Sympa Solar Power 8 MW,,,Panchagarh_132kV,8,
,Energypac Power Venture Thakurgaon Ltd.,,,Thakurgaon_132kV,115,
,Intraco Solar 30 MW,,,Lalmonirhat_132kV,30,
,Teesta Solar Limited,,,TeestaSolar_132kV,200,
"""

# ---------------------------------------------------------------------------
# MARGINAL COST REFERENCE  (from artifact f62ef837)
# ---------------------------------------------------------------------------
MC_REF = {
    "CCGT": {
        "gas":    [(200, 24.1), (350, 21.6), (450, 20.5)],
        "liquid": [(200, 37.6), (350, 34.4), (450, 31.8)],
    },
    "OCGT": {
        "gas":    [(50, 40.6), (100, 37.5), (200, 35.1)],
        "liquid": [(50, 72.8), (100, 64.9), (200, 58.4)],
    },
    "ICE": {
        "gas":    [(10, 37.2), (50, 34.0), (100, 31.3)],
        "liquid": [(10, 46.9), (50, 43.0), (100, 40.6)],
    },
    "Steam Turbine": {
        "gas":    [(100, 39.9), (300, 36.6), (600, 33.6)],
        "liquid": [(100, 55.0), (300, 50.1), (600, 46.2)],
        "coal":   [(100, 28.8), (300, 26.1), (600, 23.3)],
    },
    "Hydro":    {"hydro": [(10, 1.5), (100, 1.5), (500, 1.5)]},
    "Solar PV": {"solar": [(10, 0.0), (100, 0.0), (500, 0.0)]},
    "Wind":     {"wind":  [(10, 0.0), (100, 0.0), (500, 0.0)]},
}

FUEL_CATEGORY = {
    "Gas":   "gas",
    "HFO":   "liquid",
    "HSD":   "liquid",
    "Coal":  "coal",
    "Solar": "solar",
    "Wind":  "wind",
    "Hydro": "hydro",
}
HSD_PREMIUM = 1.10


def log_linear_interp(p: float, points: list) -> float:
    ps = np.array([pt[0] for pt in points], dtype=float)
    cs = np.array([pt[1] for pt in points], dtype=float)
    if np.all(cs == cs[0]):
        return float(cs[0])
    log_ps = np.log(ps)
    log_cs = np.log(np.where(cs == 0, 1e-9, cs))
    log_p  = np.log(max(p, 0.1))
    if log_p <= log_ps[0]:
        slope = (log_cs[1] - log_cs[0]) / (log_ps[1] - log_ps[0])
        log_c = log_cs[0] + slope * (log_p - log_ps[0])
    elif log_p >= log_ps[-1]:
        slope = (log_cs[-1] - log_cs[-2]) / (log_ps[-1] - log_ps[-2])
        log_c = log_cs[-1] + slope * (log_p - log_ps[-1])
    else:
        log_c = np.interp(log_p, log_ps, log_cs)
    result = np.exp(log_c)
    if np.all(cs == 0):
        return 0.0
    return round(float(result), 2)


def calc_marginal_cost(p_nom: float, tech: str, fuel: str):
    """Return single USD/MWh using the PRIMARY fuel (first listed for dual-fuel)."""
    if not tech or tech == "Import" or not fuel or fuel == "Import":
        return None
    if not p_nom or pd.isna(p_nom) or p_nom <= 0:
        return None
    primary_fuel = fuel.split("/")[0].strip()
    fuel_cat = FUEL_CATEGORY.get(primary_fuel)
    if fuel_cat is None:
        return None
    tech_ref = MC_REF.get(tech)
    if tech_ref is None or fuel_cat not in tech_ref:
        return None
    cost = log_linear_interp(p_nom, tech_ref[fuel_cat])
    if primary_fuel == "HSD":
        cost = round(cost * HSD_PREMIUM, 2)
    return cost


# ---------------------------------------------------------------------------
# TECHNOLOGY LOOKUP  (same as generate_generator_data.py)
# ---------------------------------------------------------------------------
TECH_LOOKUP = {
    "Madanganj-55 MW PP(Summit)":                "ICE",
    "Siddhirganj 210 MW TPP":                    "Steam Turbine",
    "Siddhirganj 2*120 MW GTPP":                 "OCGT",
    "Gagnagar 102 MW PP (Digital Power)":        "ICE",
    "Kamalaghat 54 MW PP(Banco Energy)":         "ICE",
    "Kodda 150 MW PP BRPL":                      "ICE",
    "Manikganj 55 MW PP (Northern)":             "ICE",
    "Nababganj 55 MW PP (Southern power )":      "ICE",
    "Summit Power Ashulia":                      "ICE",
    "Summit Power Madhabdi":                     "ICE",
    "Gazipur 52 MW PP":                          "ICE",
    "Tongi 80 MW GTPP":                          "OCGT",
    "Kodda 300 MW PP Unit-2 (Summit)":           "ICE",
    "Kodda 149 MW PP Unit-1 (Summit)":           "ICE",
    "Gazipur 100 MW PP":                         "ICE",
    "Meghnaghat 104 MW PP (OPCL)":               "ICE",
    "Manikgonj 162MW PP(MPGL)":                  "ICE",
    "Spectra Solar Plant Ltd.":                  "Solar PV",
    "Kanchan Purbachal Power Generation Ltd.":   "ICE",
    "Unique Meghnaghat Power Limited (UMPL)":    "CCGT",
    "JERA Meghnaghat Power Limited":             "CCGT",
    "Sreepur 150 MW PP BRPL":                    "ICE",
    "Chattogram TPP":                            "Steam Turbine",
    "Raozan 25 MW PP":                           "ICE",
    "Teknaf  20MW PP (Solartech)":               "Solar PV",
    "Patenga 50MW PP (Baraka)":                  "ICE",
    "Karnaphuli Hydro PP Unit-1,2,3,4, 5":       "Hydro",
    "Sikalbaha 225MW CCPP":                      "CCGT",
    "Sikalbaha Peaking GT":                      "OCGT",
    "Sikalbaha 105 MW PP (Baraka Sikalbaha)":    "ICE",
    "Hathazari 100 MW peaking PP":               "ICE",
    "Dohazari -Kalaish 100 MW Peaking":          "ICE",
    "Juldah 100 MW PP Unit-3 (Acorn)":           "ICE",
    "Malancha, Ctg. EPZ (United)":               "ICE",
    "Chattogram 108 MW PP (ECPV)":               "ICE",
    "Kaptai 7 MW  Solar PP":                     "Solar PV",
    "Anwara 300 MW PP (United)":                 "ICE",
    "Zodiac Power":                              "ICE",
    "Karnaphuli Power Ltd.":                     "ICE",
    "Juldah unit-2 (Acorn)":                     "ICE",
    "Anlima Energy Ltd.":                        "ICE",
    "Mirsharai 150 MW BRPL":                     "ICE",
    "SS Power":                                  "Steam Turbine",
    "Cox's Bazar Wind":                          "Wind",
    "Matarbari 2*600 MW (CPGCBL)":               "Steam Turbine",
    "Ashuganj TSK 50 MW PP":                     "ICE",
    "Ashuganj 55 MW PP (Precision)":             "ICE",
    "Ashuganj 195 MW PP (APSCL-United)":         "ICE",
    "Ashuganj 51 MW PP (Midland)":               "ICE",
    "Ashuganj 150MW PP (Midland)":               "ICE",
    "Titas 50 MW Peaking PP":                    "ICE",
    "Chandpur 150 MW CCPP":                      "CCGT",
    "Chandpur 200MW (Desh energy)":              "ICE",
    "Jangalia 52 MW PP (Lakdanavi)":             "ICE",
    "Cumilla 25 MW PP (Summit)":                 "ICE",
    "Feni Lanka Power":                          "ICE",
    "Chowmuhani 113 MW":                         "ICE",
    "Chandpur 115(Doreen)":                      "ICE",
    "Sonagazi 75 MW (AC) Solar Power Plant":     "Solar PV",
    "Sarishabari 3 MW Solar Plant":              "Solar PV",
    "Mymensingh 200 MW PP (United)":             "ICE",
    "Jamalpur 115 MW PP (United)":               "ICE",
    "Sutiakhali 50 MW Solar PP":                 "Solar PV",
    "Tangail Palli Power Gen 22 MW":             "ICE",
    "Bhairab 54.5 MW":                           "ICE",
    "Moulvibazar 10 MW Solar Power Plant":       "Solar PV",
    "Shahjibazar GTPP Unit- 8 & 9":             "OCGT",
    "Shahjibazar 86MW PP (Shahjibazar)":         "ICE",
    "Shahjibazar 100 MW GTPP":                   "OCGT",
    "Sylhet  20 MW GTPP":                        "OCGT",
    "Shahjahanulla 25 MW PP":                    "ICE",
    "Bibiyana South 400 MW":                     "CCGT",
    "Bheramara GTPP Unit-3":                     "OCGT",
    "Faridpur 50 MW Peaking PP":                 "ICE",
    "Gopalganj 100 MW Peaking PP":               "ICE",
    "Rupsha 105 MW PP (Orion rupsha)":           "ICE",
    "Madhumati 100 MW PP":                       "ICE",
    "Mongla Orion 100 MW Solar PP":              "Solar PV",
    "Rampal 1320 MW (BIFPCL)":                   "Steam Turbine",
    "Patuakhali 1320 MW (RNPL)":                 "Steam Turbine",
    "Barisal 110 MW PP (Summit )":               "ICE",
    "Bhola  33 MW PP (Venture)":                 "ICE",
    "Bhola 225 MW  CCPP":                        "CCGT",
    "Payra 1320 MW":                             "Steam Turbine",
    "Bhola Nutan Biddut BD LTD":                 "CCGT",
    "United Payra Power Ltd.":                   "ICE",
    "Barisal 307 MW":                            "Steam Turbine",
    "Barisal 1 MW Solar Plant":                  "Solar PV",
    "Pabna 64 MW Solar Plant":                   "Solar PV",
    "Baghabari 71 MW GTPP":                      "OCGT",
    "Baghabari  100 MW GTPP":                    "OCGT",
    "Baghabari  50 MW Peaking PP":               "ICE",
    "Bera 70 MW Peaking PP":                     "ICE",
    "Katakhali 50 MW Peaking PP":                "ICE",
    "Santahar  50 MW Peaking PP":                "ICE",
    "Natore 52 MW PP (Rajlanka)":                "ICE",
    "Chapainawabganj 100 MW Peaking PP":         "ICE",
    "Bagura 113 MW PP (Confidence)-2":           "ICE",
    "Bagura 113 MW PP (Confidence)-1":           "ICE",
    "Sirajganj 6.55 MW Solar":                   "Solar PV",
    "Sirajganj 68 MW Solar Park":                "Solar PV",
    "Pabna Solar 100 MW":                        "Solar PV",
    "Sirajganj 2 MW Wind Power Plant":           "Wind",
    "Saidpur 150 MW Simple Cycle Power Plant":   "OCGT",
    "Barapukuria TPP Unit-1 & 2":                "Steam Turbine",
    "Barapukuria 275 MW TPP Unit-3":             "Steam Turbine",
    "Rangpur 20 MW  GTPP":                       "OCGT",
    "Saidpur 20 MW GTPP":                        "OCGT",
    "Rangpur 113 MW PP (Confidence)":            "ICE",
    "Sympa Solar Power 8 MW":                    "Solar PV",
    "Energypac Power Venture Thakurgaon Ltd.":   "ICE",
    "Intraco Solar 30 MW":                       "Solar PV",
    "Teesta Solar Limited":                      "Solar PV",
}

# ---------------------------------------------------------------------------
# FUEL LOOKUP  (primary fuel used for single marginal_cost)
# Dual-fuel kept as original string; primary (first) fuel drives the cost.
# ---------------------------------------------------------------------------
FUEL_LOOKUP = {
    "Ghorasal Repowered CCPP Unit-3":            "Gas",
    "Ghorasal Repowered CCPP Unit-4":            "Gas",
    "Ghorasal TPP Unit-5":                       "Gas",
    "Ghorasal 365 MW CCPP Unit-7":               "Gas",
    "Ghorashal 108 MW PP (Regent)":              "Gas",
    "Haripur GTPP":                              "Gas",
    "Haripur 412 MW CCPP":                       "Gas",
    "Meghnaghat 450 MW CCPP (MPL)":              "Gas",
    "Meghnaghat CCPP(Summit)":                   "Gas",
    "Madanganj-55 MW PP(Summit)":                "HFO",
    "Siddhirganj 210 MW TPP":                    "Gas",
    "Siddhirganj 2*120 MW GTPP":                 "Gas",
    "Siddhirganj 335 MW CCPP":                   "Gas",
    "Gagnagar 102 MW PP (Digital Power)":        "HFO",
    "Kamalaghat 54 MW PP(Banco Energy)":         "HFO",
    "Kodda 150 MW PP BRPL":                      "HFO",
    "Manikganj 55 MW PP (Northern)":             "HFO",
    "Nababganj 55 MW PP (Southern power )":      "HFO",
    "Summit Power Ashulia":                      "Gas",
    "Summit Power Madhabdi":                     "Gas",
    "Gazipur 52 MW PP":                          "HFO",
    "Tongi 80 MW GTPP":                          "Gas",
    "Kodda 300 MW PP Unit-2 (Summit)":           "HFO",
    "Kodda 149 MW PP Unit-1 (Summit)":           "HFO",
    "Gazipur 100 MW PP":                         "HFO",
    "Meghnaghat 104 MW PP (OPCL)":               "HFO",
    "Manikgonj 162MW PP(MPGL)":                  "HFO",
    "Spectra Solar Plant Ltd.":                  "Solar",
    "Kanchan Purbachal Power Generation Ltd.":   "HFO",
    "Unique Meghnaghat Power Limited (UMPL)":    "Gas",
    "Meghnaghat CCPP(Summit)-2":                 "Gas/HSD",
    "JERA Meghnaghat Power Limited":             "Gas",
    "Sreepur 150 MW PP BRPL":                    "HFO",
    "Chattogram TPP":                            "Gas",
    "Raozan 25 MW PP":                           "HFO",
    "Teknaf  20MW PP (Solartech)":               "Solar",
    "Patenga 50MW PP (Baraka)":                  "HFO",
    "Karnaphuli Hydro PP Unit-1,2,3,4, 5":       "Hydro",
    "Sikalbaha 225MW CCPP":                      "Gas/HSD",
    "Sikalbaha Peaking GT":                      "Gas/HSD",
    "Sikalbaha 105 MW PP (Baraka Sikalbaha)":    "HFO",
    "Hathazari 100 MW peaking PP":               "HFO",
    "Dohazari -Kalaish 100 MW Peaking":          "HFO",
    "Juldah 100 MW PP Unit-3 (Acorn)":           "HFO",
    "Malancha, Ctg. EPZ (United)":               "Gas",
    "Chattogram 108 MW PP (ECPV)":               "HFO",
    "Kaptai 7 MW  Solar PP":                     "Solar",
    "Anwara 300 MW PP (United)":                 "HFO",
    "Zodiac Power":                              "HFO",
    "Karnaphuli Power Ltd.":                     "HFO",
    "Juldah unit-2 (Acorn)":                     "HFO",
    "Anlima Energy Ltd.":                        "HFO",
    "Mirsharai 150 MW BRPL":                     "HFO/Gas",
    "SS Power":                                  "Coal",
    "Cox's Bazar Wind":                          "Wind",
    "Matarbari 2*600 MW (CPGCBL)":               "Coal",
    "Ashuganj CCPP 225 MW":                      "Gas",
    "Ashuganj 450 MW CCPP(North)":               "Gas",
    "Ashuganj 450 MW CCPP(South)":               "Gas",
    "Ashuganj 420 MW CCPP(East)":                "Gas",
    "Ashuganj TSK 50 MW PP":                     "Gas",
    "Ashuganj 55 MW PP (Precision)":             "Gas",
    "Ashuganj 195 MW PP (APSCL-United)":         "Gas",
    "Ashuganj 51 MW PP (Midland)":               "Gas",
    "Ashuganj 150MW PP (Midland)":               "HFO",
    "Titas 50 MW Peaking PP":                    "HFO",
    "Chandpur 150 MW CCPP":                      "Gas",
    "Chandpur 200MW (Desh energy)":              "HFO",
    "Jangalia 52 MW PP (Lakdanavi)":             "HFO",
    "Cumilla 25 MW PP (Summit)":                 "Gas",
    "Feni Lanka Power":                          "HFO",
    "Chowmuhani 113 MW":                         "HFO",
    "Chandpur 115(Doreen)":                      "HFO",
    "Sonagazi 75 MW (AC) Solar Power Plant":     "Solar",
    "RPCL 210MW CCPP":                           "Gas",
    "Sarishabari 3 MW Solar Plant":              "Solar",
    "Mymensingh 200 MW PP (United)":             "HFO",
    "Jamalpur 115 MW PP (United)":               "HFO",
    "Sutiakhali 50 MW Solar PP":                 "Solar",
    "Tangail Palli Power Gen 22 MW":             "HFO",
    "Bhairab 54.5 MW":                           "HFO",
    "Moulvibazar 10 MW Solar Power Plant":       "Solar",
    "Fenchugonj CCPP Phase-1":                   "Gas",
    "Fenchugonj CCPP Phase-2":                   "Gas",
    "Kushiara 163 MW CCPP (KP)":                 "Gas",
    "Shajibazar 330 MW CCPP":                    "Gas",
    "Shahjibazar GTPP Unit- 8 & 9":              "Gas",
    "Shahjibazar 86MW PP (Shahjibazar)":         "Gas",
    "Shahjibazar 100 MW GTPP":                   "Gas",
    "Sylhet 225 MW CCPP":                        "Gas",
    "Sylhet  20 MW GTPP":                        "Gas",
    "Shahjahanulla 25 MW PP":                    "Gas",
    "Bibiana-II 341 MW CCPP (Summit)":           "Gas",
    "Bibiyana-III 400 MW CCPP":                  "Gas",
    "Bibiyana South 400 MW":                     "Gas",
    "Bheramara GTPP Unit-3":                     "HSD",
    "Faridpur 50 MW Peaking PP":                 "HFO",
    "Khulna 225 MW CCPP":                        "HSD/Gas",
    "Gopalganj 100 MW Peaking PP":               "HFO",
    "Bheramara 410 MW CCPP":                     "Gas",
    "Rupsha 105 MW PP (Orion rupsha)":           "HFO",
    "Madhumati 100 MW PP":                       "HFO",
    "Mongla Orion 100 MW Solar PP":              "Solar",
    "Khulna 330 MW CCPP":                        "HSD/Gas",
    "Rampal 1320 MW (BIFPCL)":                   "Coal",
    "Patuakhali 1320 MW (RNPL)":                 "Coal",
    "Barisal 110 MW PP (Summit )":               "HFO",
    "Bhola  33 MW PP (Venture)":                 "Gas",
    "Bhola 225 MW  CCPP":                        "Gas",
    "Payra 1320 MW":                             "Coal",
    "Bhola Nutan Biddut BD LTD":                 "Gas/HSD",
    "United Payra Power Ltd.":                   "HFO",
    "Barisal 307 MW":                            "Coal",
    "Barisal 1 MW Solar Plant":                  "Solar",
    "Pabna 64 MW Solar Plant":                   "Solar",
    "Baghabari 71 MW GTPP":                      "Gas",
    "Baghabari  100 MW GTPP":                    "Gas",
    "Baghabari  50 MW Peaking PP":               "HFO",
    "Bera 70 MW Peaking PP":                     "HFO",
    "Katakhali 50 MW Peaking PP":                "HFO",
    "Sirajganj 225MW CCPP Unit-1":               "Gas/HSD",
    "Sirajganj 225MW CCPP Unit-2":               "Gas/HSD",
    "Sirajganj 225MW CCPP Unit-3":               "Gas/HSD",
    "Sirajganj 400 MW CCPP Unit-4":              "Gas/HSD",
    "Santahar  50 MW Peaking PP":                "HFO",
    "Natore 52 MW PP (Rajlanka)":                "HFO",
    "Chapainawabganj 100 MW Peaking PP":         "HFO",
    "Bagura 113 MW PP (Confidence)-2":           "HFO",
    "Bagura 113 MW PP (Confidence)-1":           "HFO",
    "Sirajganj 6.55 MW Solar":                   "Solar",
    "Sirajganj 68 MW Solar Park":                "Solar",
    "Pabna Solar 100 MW":                        "Solar",
    "Sirajganj 2 MW Wind Power Plant":           "Wind",
    "Saidpur 150 MW Simple Cycle Power Plant":   "HSD",
    "Barapukuria TPP Unit-1 & 2":                "Coal",
    "Barapukuria 275 MW TPP Unit-3":             "Coal",
    "Rangpur 20 MW  GTPP":                       "HSD",
    "Saidpur 20 MW GTPP":                        "HSD",
    "Rangpur 113 MW PP (Confidence)":            "HFO",
    "Sympa Solar Power 8 MW":                    "Solar",
    "Energypac Power Venture Thakurgaon Ltd.":   "HFO",
    "Intraco Solar 30 MW":                       "Solar",
    "Teesta Solar Limited":                      "Solar",
}

# ---------------------------------------------------------------------------
# BUILD DATAFRAME
# ---------------------------------------------------------------------------
df = pd.read_csv(io.StringIO(RAW))
df.columns = ["Area", "Name", "Technology", "Fuel", "Bus", "p_nom", "marginal_cost"]
df["Area"] = df["Area"].replace("", np.nan).ffill()
df["p_nom"] = pd.to_numeric(df["p_nom"], errors="coerce")

# Populate Technology and Fuel from lookups (keep existing tech if present)
def resolve_tech(row):
    existing = str(row["Technology"]).strip()
    if existing and existing.lower() not in ("nan", ""):
        return existing
    return TECH_LOOKUP.get(row["Name"].strip(), "Unknown")

def resolve_fuel(row):
    return FUEL_LOOKUP.get(row["Name"].strip(), "Unknown")

df["Technology"] = df.apply(resolve_tech, axis=1)
df["Fuel"]       = df.apply(resolve_fuel, axis=1)

# Compute marginal cost
df["marginal_cost"] = df.apply(
    lambda r: calc_marginal_cost(r["p_nom"], r["Technology"], r["Fuel"]),
    axis=1
)

# Rename for output
df_out = df.rename(columns={
    "p_nom":          "Present Capacity (MW)",
    "marginal_cost":  "Marginal Cost (USD/MWh)",
})

df_out.to_csv(OUT_CSV, index=False)
print(f"Wrote {len(df_out)} rows → {OUT_CSV}")

# Sanity checks
print(f"\nUnknown technology: {(df_out['Technology'] == 'Unknown').sum()}")
print(f"Unknown fuel:       {(df_out['Fuel'] == 'Unknown').sum()}")
print(f"Blank marginal cost:{df_out['Marginal Cost (USD/MWh)'].isna().sum()}")

print("\nTechnology breakdown:")
print(df_out["Technology"].value_counts().to_string())

print("\nSample rows:")
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 160)
print(df_out[["Name","Technology","Fuel","Present Capacity (MW)","Marginal Cost (USD/MWh)"]].head(15).to_string(index=False))
