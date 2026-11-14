# Field Shift: 3-minute demo script

Live site: https://nasa01-c2bd2.web.app · Farmer link: https://nasa01-c2bd2.web.app/farm · Telegram: @agro01bot

**Before you start**
- Open the four tabs in this order: `/farm`, `/` (dashboard), `/backtest`, `/data`.
- On `/farm`, press English and clear the place, so the demo starts fresh.
- Have a phone ready with the farmer link open, to hold up during part 1.
- The site works offline once opened. If the venue Wi-Fi drops, keep going.

---

## 0:00–0:20 · The problem
> "Sri Lankan farmers mostly grow paddy, then paddy again, because everyone else does. When many switch at once, prices crash. And the government only learns what was planted after the harvest. Field Shift uses NASA data to advise each farmer, and adds those choices up for the country before the season starts."

## 0:20–1:10 · Farmer link (`/farm`)
1. Tap **සිංහල**, then **தமிழ்**.
   > "Farmers use it in their own language."

   Switch back to English.
2. Tap **📍 Use my location**, or type *Anuradhapura*.
   > "No sign-up. GPS, or type a village name."
3. Leave **Tank or canal** and **More income** selected. Tap **Show my best crops**.
4. Point at the top card: Maha green chilli, then Yala cowpea, with the money range.
   > "It ranks rotations on profit, risk, water, soil and erosion. It never shows a plan that loses money, and it warns when water may run short."
5. Tap **I will grow this**.
   > "That choice now reaches the agriculture officer and the national dashboard. Farmers without smartphones get the same answers through our Telegram bot, which stands in for SMS."

## 1:10–1:50 · Government dashboard (`/`)
1. Point at the tiles: paddy production, rice self-sufficiency, nitrogen fertilizer need, calories covered.
   > "This is the whole country's season, before harvest: surplus or deficit per crop, and fertilizer to import."
2. Drag **Seasonal rainfall** to −20 %, then **Fertilizer supply** to −50 %.
   > "What-if: a dry season plus a fertilizer shortage. Here's the production gap, live."

   Reset both sliders.
3. Switch the map to **Rain 2021 (GPM IMERG)** or **Slope (SRTM)**.
   > "District layers come straight from NASA satellites."

## 1:50–2:40 · Proof: the 2021 test (`/backtest`)
> "We trained only on data up to 2020, then checked 2021, a year the model never saw."

1. Point at the error tiles: paddy yield error is about **0.43–0.50 t/ha**.
2. In the with/without table, choose **30 % of area**:
   - Farm income: **151.2 → 157.2 bn LKR (+4 %)**
   - Irrigation water: **5,740 → 5,647 million m³ (−1.6 %)**
   - Nitrogen fertilizer: **136,475 → 135,863 t**
   > "And this is with a market check. Without it, everyone would rush into chilli and cowpea and crash their prices by 75 %. The app stops recommending a crop once its national price would fall more than 15 %."

## 2:40–3:00 · NASA data (`/data`)
> "Five NASA datasets, plus open soil and forecast data, each with a job.
> - NASA POWER and GPM IMERG drive the yield model.
> - SRTM slope sets the erosion risk.
> - MODIS NDVI and SMAP soil moisture show crop and soil condition.
> - Open-Meteo adds the next-season forecast and 2040s climate projections.
>
> Field Shift: the right crop for each field, and a country that knows its harvest before it happens."

---

## If judges ask
- **"Did the satellite rain improve the model?"**
  On 2011–2020 validation, yes: IMERG gave the lowest error (0.508 t/ha, against 0.514 for history only). On 2021 itself, history alone was slightly better (0.434 against 0.498 for Maha). We show this openly on the Data page. IMERG's main gain is separating hill districts that NASA POWER's 50 km grid treats as one.
- **"Is the 'with app' result real?"**
  It's a simulation on 2021 data: real 2021 areas, yields, weather and prices, with farmers switching under stated rules. The assumptions are listed on the 2021 test page.
- **"What about farmers without smartphones?"**
  - The Telegram bot gives the same answers in text.
  - Officers can enter plans on the Officer desk.
  - The site works offline.
- **"How would this scale?"**
  The district data packs are small JSON files. One rebuild script refreshes everything from NASA each season.

## Notes for the team
- The Sinhala and Tamil text was drafted without a native speaker's review. Ask a native speaker, ideally an agricultural instructor, to check it before real farmers use it.
- Some numbers will change slightly when the MODIS NDVI and SMAP downloads are added. Re-read the tiles on the day of the pitch.
- The Telegram bot and API currently run on one laptop. Keep it on and awake during judging.
