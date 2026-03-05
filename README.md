# E.ON Meter Data for Home Assistant (ha-eon-meter)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-1.2.1-blue.svg?style=for-the-badge)](https://github.com/Aiasz/ha-eon-meter)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg?style=for-the-badge)](LICENSE)

Egy Home Assistant integráció (Custom Component) az E.ON okos fogyasztásmérők (Smart Meter) adatainak lekérdezésére és megjelenítésére — IMAP e-mail fiókból és/vagy helyi API-n keresztül.

---

## 🌟 Funkciók

- **Több adatforrás (Hibrid működés):**
  - **Email (IMAP) mód:** Az E.ON által küldött hivataos Excel (`.xlsx`) fájlok automatikus letöltése és feldolgozása e-mail fiókból.
  - **API mód:** Adatok lekérdezése helyi vagy távoli API-n keresztül JSON formátumban.
  - **Hibrid mód:** Mindkét forrás egyidejű használata okos adategyesítéssel, deduplikációval és utólagos adatpótlással (backfill).
- **25 szenzor entitás:**
  - Napi / Heti / Havi import és export fogyasztás
  - Import / Export összesített (Total) számláló
  - Mérőóra OBIS állások (Import, Export, T1, T2)
  - Csúcsteljesítmény T1 / T2
  - Reaktív energia (import/export napi)
  - Napi nettó egyenleg, Napi csúcsterhelés
  - Önellátási arány (%)
  - Becsült napi költség (Ft)
  - Napi fogyasztás bontás (attribútumban napi bontás)
  - Utolsó kiesés, API/IMAP státusz, Utolsó lekérdezés, Utolsó adat időbélyege
- **Adattárolás:** Feldolgozott adatok perzisztensen tárolódnak — HA újraindítás után sem vész el a buffer.
- **E-mail utófeldolgozás:** Feldolgozás után a levél megtartható, törölhető vagy egy másik IMAP-mappába helyezhető.
- **Újrakonfigurálás:** Minden beállítás (e-mail szerver, villanydíj, levél sorsa, frissítési időköz) módosítható újraindítás nélkül a Configure gombbal.

---

## 📥 Telepítés

### HACS (ajánlott)

1. HACS → Integrations → `...` → **Custom repositories**
2. URL: `https://github.com/Aiasz/ha-eon-meter` — kategória: **Integration**
3. Telepítés után indítsd újra a HA-t

### Manuális

1. Töltsd le (`Code` → `Download ZIP`)
2. Másold a `custom_components/eon_meter` mappát a HA `config/custom_components/` könyvtárába
3. Indítsd újra a HA-t

---

## ⚙️ Beállítás

Settings → Devices & Services → **Add Integration** → *E.ON Meter Data*

1. **Adatforrás** kiválasztása: `Email`, `API`, vagy `API & Email`
2. **E-mail beállítások** (IMAP mód esetén):
   - Host: pl. `imap.gmail.com` vagy `outlook.office365.com`
   - Port: `993` (SSL)
   - Tárgy szűrő: a levél tárgya, pl. `Villanyóra Smart Meter Adatok`
3. **E-mail levél sorsa** feldolgozás után:

| Beállítás | Leírás |
|-----------|--------|
| `keep` | Megőrzés — bent marad a beérkező levelek közt |
| `delete` | Törlés — véglegesen törli a levelet |
| `move` | Áthelyezés — a megadott IMAP-mappába kerül (alapból: `Archív`); ha nem létezik, az integráció létrehozza |

4. **Villanydíj** (Ft/kWh): a becsült napi költség kiszámításához
5. **Frissítési időköz** (másodperc): pl. `3600` = 1 óra

> Beállítások bármikor módosíthatók: Settings → Devices & Services → E.ON Meter → **Configure** (újraindítás nélkül)

---

## 📊 Szenzor lista

| Entitás | Leírás |
|---------|--------|
| `sensor.e_on_meter_import_daily` | Import fogyasztás – mai nap (kWh) |
| `sensor.e_on_meter_export_daily` | Export termelés – mai nap (kWh) |
| `sensor.e_on_meter_import_weekly` | Import – ezen a héten (kWh) |
| `sensor.e_on_meter_export_weekly` | Export – ezen a héten (kWh) |
| `sensor.e_on_meter_import_monthly` | Import – ebben a hónapban (kWh) |
| `sensor.e_on_meter_export_monthly` | Export – ebben a hónapban (kWh) |
| `sensor.e_on_meter_import_total` | Import összesített számláló (kWh) |
| `sensor.e_on_meter_export_total` | Export összesített számláló (kWh) |
| `sensor.e_on_meter_napi_netto_egyenleg` | Import − Export egyenleg aznap (kWh) |
| `sensor.e_on_meter_napi_csucsterheles` | Napi csúcsterhelés (kW) |
| `sensor.e_on_meter_onellatasi_arany` | Önellátási arány (%) |
| `sensor.e_on_meter_becsult_napi_koltseg` | Becsült napi villanyszámla (Ft) |
| `sensor.e_on_meter_napi_fogyasztas_bontas` | Napi import/export bontás (attribútumban) |
| `sensor.e_on_meter_meroora_import_allas` | OBIS mérőóra import állás (kWh) |
| `sensor.e_on_meter_meroora_export_allas` | OBIS mérőóra export állás (kWh) |
| `sensor.e_on_meter_meroora_t1_import_allas` | OBIS T1 tarifa import állás (kWh) |
| `sensor.e_on_meter_meroora_t2_import_allas` | OBIS T2 tarifa import állás (kWh) |
| `sensor.e_on_meter_csucsteljesitmeny_t1` | Csúcsteljesítmény T1 (kW) |
| `sensor.e_on_meter_csucsteljesitmeny_t2` | Csúcsteljesítmény T2 (kW) |
| `sensor.e_on_meter_import_reaktiv_daily` | Reaktív import energia – napi (kVArh) |
| `sensor.e_on_meter_export_reaktiv_daily` | Reaktív export energia – napi (kVArh) |
| `sensor.e_on_meter_last_outage` | Utolsó áramkimaradás időpontja |
| `sensor.e_on_meter_api_imap_status` | Integráció státusz / utolsó hiba |
| `sensor.e_on_meter_utolso_lekerdezes` | Következő lekérdezés ideje |
| `sensor.e_on_meter_utolso_adat_idobelyege` | Legutóbb feldolgozott adat időbélyege |

---

## 🎨 Dashboard kártyák

A `lovelace_cards.yaml` fájl 15 kész kártyát tartalmaz — egyenként illeszthetők be a dashboardba.

**Beillesztés:** Dashboard → Add Card → Manual card → másold be a kártya YAML-ját.

### Szükséges HACS frontend kiegészítők (opcionálisak)

| Kiegészítő | HACS keresőnév | Kártyák amelyek használják |
|------------|---------------|---------------------------|
| mini-graph-card | `mini-graph-card` | 5, 6, 13 |
| apexcharts-card | `apexcharts-card` | 10 |
| Mushroom | `Mushroom` | 1, 2 |

> A többi kártya (3, 4, 7, 8, 9, 11, 12, 14, 15) **beépített HA kártya** — semmit sem kell telepíteni hozzájuk.

---

### Kártya példák

#### Státusz chip-sor
```yaml
type: custom:mushroom-chips-card
chips:
  - type: entity
    entity: sensor.e_on_meter_api_imap_status
    icon: mdi:check-network
    icon_color: green
  - type: entity
    entity: sensor.e_on_meter_utolso_lekerdezes
    icon: mdi:clock-sync-outline
  - type: entity
    entity: sensor.e_on_meter_utolso_adat_idobelyege
    icon: mdi:database-clock-outline
```

#### Mai legfontosabb adatok
```yaml
type: glance
title: "Mai adatok"
show_name: true
show_icon: true
show_state: true
entities:
  - entity: sensor.e_on_meter_import_daily
    name: "Import"
    icon: mdi:transmission-tower-import
  - entity: sensor.e_on_meter_export_daily
    name: "Export"
    icon: mdi:solar-power-variant
  - entity: sensor.e_on_meter_napi_csucsterheles
    name: "Csúcs"
    icon: mdi:lightning-bolt-circle
  - entity: sensor.e_on_meter_becsult_napi_koltseg
    name: "Költség"
    icon: mdi:cash
```

#### Import / Export – 7 napos trend
```yaml
type: custom:mini-graph-card
title: "Import / Export – 7 nap"
icon: mdi:chart-line
hours_to_show: 168
points_per_hour: 0.04
line_width: 2
smoothing: true
show:
  labels: false
  points: false
  legend: true
  fill: true
entities:
  - entity: sensor.e_on_meter_import_daily
    name: "Import"
    color: "#e74c3c"
  - entity: sensor.e_on_meter_export_daily
    name: "Export"
    color: "#2ecc71"
```

#### Napi nettó egyenleg – 14 napos trend
```yaml
type: custom:mini-graph-card
title: "Napi Nettó Egyenleg – 14 nap"
icon: mdi:scale-balance
hours_to_show: 336
points_per_hour: 0.03
line_width: 2
smoothing: true
color_thresholds:
  - value: -999
    color: "#2ecc71"
  - value: 0
    color: "#e74c3c"
show:
  fill: true
  extrema: true
  labels: true
  legend: false
entities:
  - entity: sensor.e_on_meter_napi_netto_egyenleg
    name: "Nettó egyenleg"
```

#### Önellátási arány – Gauge
```yaml
type: gauge
title: "Önellátási Arány"
entity: sensor.e_on_meter_onellatasi_arany
unit: "%"
min: 0
max: 100
needle: true
severity:
  green: 60
  yellow: 30
  red: 0
```

#### Összesítő táblázat
```yaml
type: entities
title: "Összesítő"
show_header_toggle: false
entities:
  - entity: sensor.e_on_meter_import_daily
    name: "Import – ma"
    icon: mdi:transmission-tower-import
  - entity: sensor.e_on_meter_export_daily
    name: "Export – ma"
    icon: mdi:solar-power-variant
  - type: divider
  - entity: sensor.e_on_meter_import_weekly
    name: "Import – ezen a héten"
  - entity: sensor.e_on_meter_export_weekly
    name: "Export – ezen a héten"
  - type: divider
  - entity: sensor.e_on_meter_import_monthly
    name: "Import – ebben a hónapban"
  - entity: sensor.e_on_meter_export_monthly
    name: "Export – ebben a hónapban"
  - type: divider
  - entity: sensor.e_on_meter_import_total
    name: "Import összesen"
    icon: mdi:counter
  - entity: sensor.e_on_meter_export_total
    name: "Export összesen"
    icon: mdi:counter
  - type: divider
  - entity: sensor.e_on_meter_becsult_napi_koltseg
    name: "Becsült napi költség"
    icon: mdi:cash-clock
```

#### Havi statisztika – oszlopdiagram (beépített)
```yaml
type: statistics-graph
title: "Havi Import vs Export"
chart_type: bar
period: month
stat_types:
  - max
entities:
  - entity: sensor.e_on_meter_import_monthly
    name: "Import (havi)"
  - entity: sensor.e_on_meter_export_monthly
    name: "Export (havi)"
```

> Az összes kártya YAML-ja megtalálható a repóban: [`lovelace_cards.yaml`](lovelace_cards.yaml)

---

## 🕓 Verziótörténet

### v1.2.0 (2026-03-05)
- 📊 **Dashboard kártyák**: `lovelace_cards.yaml` — 15 kész kártya a repóban, egyenként beilleszthető
- 📋 **Teljes szenzor lista** a README-ben, valós entity ID-kkal (`sensor.e_on_meter_*`)
- 📖 **README átírva**: telepítés, beállítás, szenzor lista, kártya példák, verziótörténet

### v1.1.0 (2026-03-05)
- 🗂️ **Brand ikonok**: `brand/` almappába kerültek (HACS / HA 2024+ spec)
- 🖼️ **SVG ikonok** hozzáadva: `brand/icon.svg`, `brand/logo.svg`
- 🌍 **Fordítási fájlok**: `strings.json`, `translations/hu.json`, `translations/en.json`
- 📬 **E-mail levél sorsa** (keep/delete/move): telepítési varázslóban és OptionsFlow-ban is beállítható
- 🔄 **Automatikus újratöltés**: Configure után nem kell kézzel újraindítani a HA-t
- 🔢 **make_assets.py** frissítve: `brand/` mappába generál, SVG-t is előállít

### v1.0.21
- Duplikált ConfigFlow javítva, brand ikon PNG, sw_version, tariff az OptionsFlow-ban

### v1.0.20
- Új szenzorok (csúcsteljesítmény, önellátási arány, becsült napi költség), T1/T2 OBIS

### v1.0.18
- E-mail áthelyezés/törlés, 2 új időbélyeg szenzor, OptionsFlow bevezetése

---

## 📜 Licenc

Ez a projekt a **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)** licenc alatt áll.

| Szabad | Feltétele |
|--------|-----------|
| ✅ Szabad felhasználás és módosítás | Hivatkozás az eredeti projektre kötelező |
| ✅ Terjesztés és megosztás | Fel kell tüntetni az eredeti szerzőt (`Aiasz / ha-eon-meter`) |
| ✅ Ingyenes személyes / otthoni használatra | — |
| ❌ Kereskedelmi felhasználásra **nem** ingyenes | Kereskedelmi célra külön engedély szükséges |

**Hivatkozás formátuma:**
```
Alapja: ha-eon-meter by Aiasz — https://github.com/Aiasz/ha-eon-meter
```

[Teljes licencszöveg (LICENSE)](LICENSE) · [CC BY-NC 4.0 összefoglaló](https://creativecommons.org/licenses/by-nc/4.0/)

---

## 👨‍💻 Készítő

Készítette: **@Aiasz**

*Ha hasznosnak találod, dobj egy csillagot a repóra! ⭐*
