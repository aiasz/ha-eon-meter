# E.ON Meter Data for Home Assistant (ha-eon-meter)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg?style=for-the-badge)](https://github.com/Aiasz/ha-eon-meter)

Egy Home Assistant integráció (Custom Component) az E.ON okos fogyasztásmérők (Smart Meter) adatainak lekérdezésére és Home Assistantban történő megjelenítésére.

## 🌟 Funkciók / Features

- **Több adatforrás támogatása (Hibrid működés):**
  - **API mód:** Adatok lekérdezése helyi vagy távoli API-n keresztül JSON formátumban.
  - **Email (IMAP) mód:** Az E.ON által küldött hivatalos Excel (`.xlsx`) fájlok automatikus letöltése és feldolgozása email fiókból.
  - **Hibrid mód:** Mindkét forrás egyidejű használata okos adategyesítéssel, deduplikációval és utólagos adatpótlással (backfill), ha az eredeti adat 0 volt.
- **Részletes Szenzorok:**
  - `Total Import` / `Total Export` (Összesített adatok)
  - Napi (`Daily`), Heti (`Weekly`) és Havi (`Monthly`) import és export fogyasztás, amik a megfelelő ciklus végén automatikusan nullázódnak.
  - `Last Outage` (Utolsó áramszünet ideje): Automatikusan detektálja, ha 15 percnél hosszabb adatkimaradás volt.
- **Nyers Adatok Tárolása:** A Total szenzorok `measurements` attribútumában a legutóbbi ~1 hét (~672 mérési pont) teljes adatsora megőrzésre kerül további grafikonos feldolgozáshoz (pl. Markdown, ApexCharts stb.).

## 📥 Telepítés (Installation)

### 1. Telepítés HACS használatával (Ajánlott)

Ez az integráció egyelőre egyedi (Custom) tárolóként adható hozzá a HACS-hez.

1. Nyisd meg a Home Assistantban a **HACS** menüpontot.
2. Kattints a jobb felső sarokban a `...` (három pont) ikonra, majd válaszd a **Custom repositories** (Egyéni tárolók) lehetőséget.
3. A *Repository* mezőbe másold be ezt az URL-t: 
   `https://github.com/Aiasz/ha-eon-meter`
4. A *Category* legördülő menüben válaszd az **Integration** típust.
5. Kattints az **Add** (Hozzáadás) gombra.
6. A listában megjelenő *E.ON Meter Data* kártyánál kattints a **Download** (Telepítés) gombra.
7. Indítsd újra (Restart) a Home Assistantot!

### 2. Manuális telepítés

1. Töltsd le az integrációt innen a GitHub-ról (`Code` -> `Download ZIP`).
2. Másold be a `custom_components/eon_meter` mappát a Home Assistantod `config/custom_components` mappájába.
3. Indítsd újra (Restart) a Home Assistantot!

## ⚙️ Beállítás (Configuration)

Az integráció a Home Assistant felületén keresztül konfigurálható.

1. Lépj ide: **Beállítások** (Settings) -> **Eszközök és szolgáltatások** (Devices & Services).
2. Kattints a jobb alsó sarokban az **Integráció hozzáadása** (Add Integration) gombra.
3. Keresd meg és válaszd ki az **E.ON Meter Data** lehetőséget.
4. Válaszd ki az adatforrást (*Adatforrás*):
   - **API Only**: Csak a helyi API lekérdezése.
   - **Email Only**: Csak az E.ON által küldött Excel fájlok feldolgozása IMAP-on keresztül.
   - **Both (API + Email)**: A kettő kombinációja.
5. Töltsd ki a kért adatokat (A kiválasztott módtól függően az API Token és az IMAP beállítások is felugranak). Példa az Email konfigurációhoz:
   - **Host:** `outlook.office365.com` / stb.
   - **Port:** Általában `993`.
   - **Tárgy szűrő (Subject):** A keresendő vizsgált levél tárgyának egy része (pl. `EON` vagy `W1000-EON`).

## � E-mail feldolgozás – levél sorsa

A beállításokban (Configure gomb) megadható, hogy mi történjen az e-maillel feldolgozás után:

| Beállítás | Leírás |
|-----------|--------|
| `keep` | Megőrzés — a levél bent marad a beérkező levelek közt |
| `delete` | Törlés — az integráció véglegesen törli a levelet |
| `move` | Áthelyezés — a megadott IMAP-mappába (pl. `Archív`) kerül; ha a mappa nem létezik, az integráció létrehozza |

A beállítás az **OptionsFlow**-ban (Settings → Devices & Services → E.ON Meter → Configure) módosítható, újraindítás nélkül érvényes.

---

## 🕓 Verziótörténet

### v1.1.0 (2026-03-05)
- 🗂️ **Brand ikonok javítva**: az ikonok és logók mostantól a `brand/` almappában vannak (HACS / HA 2024+ spec szerint)
- 🖼️ **SVG ikonok hozzáadva**: `brand/icon.svg` és `brand/logo.svg` vektoros változatok
- 🌍 **Fordítási fájlok**: `strings.json`, `translations/hu.json`, `translations/en.json` — a config flow mezők mostantól olvasható magyarul/angolul jelennek meg
- 📬 **E-mail levél sorsa** (keep/delete/move): már a telepítési varázslóban és az OptionsFlow-ban is megadható, megfelelő leírásokkal
- 🔄 **Automatikus újratöltés**: ha a beállításokban (Configure) módosítasz valamit (pl. email_action, villanydíj, scan_interval), az integráció automatikusan újratölti magát — nem kell kézzel újraindítani
- 🔢 **make_assets.py** frissítve: a `brand/` almappába generál, SVG állományokat is előállít
- Készítő: Aiasz

### v1.0.21
- Duplikált ConfigFlow javítva, brand ikon PNG, sw_version button.py, tariff az OptionsFlow-ban

### v1.0.20
- Új szenzorok (csúcsteljesítmény, önellátási arány, becsült napi költség), T1/T2 OBIS, logó eszközök

### v1.0.18
- E-mail áthelyezés/törlés funkció, 2 új időbélyeg szenzor, OptionsFlow bevezetése

---

## �👨‍💻 Készítő

Készítette: **@Aiasz**

*Ha hasznosnak találod, dobj egy csillagot a repóra! ⭐*
