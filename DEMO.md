# HospitalShield AI - Demo Script

## 3-Minute Script

**0:00-0:30**
- Start on the **Overview** (Command Center).
- Explain the problem and persona: "A hospital planner asks: if an extreme weather event hits, which constraints bind us, and what actions actually help?"
- Note the SYNTHETIC baseline label on all data points.

**0:30-1:10**
- Navigate to **Hospital Twin**.
- Select the `heatwave_power_outage` or `flood_storm_access` scenario.
- Scrub the time slider to see occupancy spike, ED boarding rise, and staff shortages compound over 72 hours.

**1:10-1:50**
- Open **Failure Points** and **Action Plan**.
- Show the first failure, its cascading effects, and the binding-constraint ribbon.
- Click an alert (e.g. `R05 power_deficit` or `R11 supply_stockout`) to see the exact hour range, threshold, and observed values.

**1:50-2:30**
- View the Action Planner Gantt chart for the ordered interventions (what, when, effective after lead time).
- Apply the plan and go to **Compare Runs**.
- Show side-by-side metrics: baseline vs. interventions, with explicit attribution rules (e.g., "Surge beds raised ward usable capacity...").

**2:30-3:00**
- Open the **Assumptions and Data** page.
- Explain provenance, the lack of real Mayo Clinic data, and the limitations of the model.
- Turn off the backend network and show the app's offline fallback using the PRECOMPUTED snapshots.

## 60-Second Backup Script
- If live demo fails, click the **Demo Mode** button in the header.
- The UI automatically loads precomputed data, shows the heatwave scenario, opens a power deficit alert, generates a plan, applies it, and opens the comparison.
