# CounselGrid: Quick-Start and Data-Privacy Guide

**For:** Managing Partner, IT Director or Legal Operations lead
**Time to install:** about 5 minutes
**Cloud accounts required:** none

---

## What this is

CounselGrid is a working prototype of a legal-operations tool for managing outside counsel. A user enters a new matter and the opposing party's name. The tool then:

1. checks every firm on the panel against a conflict registry and disqualifies any firm that actively represents the opposing party,
2. flags firms with a past relationship that would need a conflict waiver,
3. ranks the remaining firms on a published 100-point scale (bench depth, cost, cybersecurity score, and fee and diversity commitments), and
4. records the decision in an audit log.

It also includes spend and rate dashboards and a searchable register of Master Service Agreements and conflict disclosures.

**It is not a legal-advice tool.** It gives no legal opinions, makes no predictions about case outcomes and is not meant for the public. Every conflict determination stays with your attorneys and ethics counsel.

**The data included is fictional.** The 30 firms, their conflicts and the 25 matters are invented for demonstration. Any resemblance to real firms or companies is unintended.

---

## Install in 3 steps

### Step 1: Install Python (skip if already installed)

Download Python 3.10 or newer from **python.org/downloads**. On Windows, tick **"Add Python to PATH"** during installation. Your IT team may prefer to use the firm's standard software-deployment process.

### Step 2: Unzip the folder

Unzip `CounselGrid-LegalOps-Handoff.zip` anywhere on the computer, for example `Documents\CounselGrid`.

### Step 3: Start it

- **Windows:** double-click **`run.bat`**.
- **Mac or Linux:** open Terminal in the folder and run **`./run.sh`**.

The first launch takes about a minute while it sets up. CounselGrid then opens in your web browser at **http://localhost:8501**. To stop it, close the terminal window. Later launches start in a few seconds.

**A 60-second tour:** on the first tab, type *Ironbridge Packaging* as the counterparty and click **Run conflict gate & rank panel**. You will see one firm disqualified, one flagged for a waiver and eleven firms ranked with the reasons for each score.

---

## Where your data goes

In the default local mode, **no data you enter leaves this computer.**

| Question | Answer |
|---|---|
| Where is the data stored? | In one file, `data/counselgrid.db`, inside the CounselGrid folder on this computer. |
| Can other computers on the network reach it? | No. The app listens only on this machine (`localhost`). Colleagues on the network cannot open it. |
| Does it send usage statistics or analytics? | No. Streamlit's usage statistics are switched off in `.streamlit/config.toml`. |
| Does it load anything from the internet while running? | No. It uses no external fonts, scripts, trackers or AI services. |
| Does it need the internet at all? | Only once, during the first launch, to download the open-source software it runs on (Streamlit, pandas, Plotly and similar) from the public Python package index. No firm or client data is sent in that step. After that it runs offline. |
| Can conflict records be altered? | No. Conflict entries are append-only. The database itself refuses edits and deletions, and corrections are logged as new entries. |
| How do we back it up or remove it? | Copy or delete `data/counselgrid.db` the same way as any other confidential file. Deleting the whole folder removes everything. |
| Is there a cloud option? | Yes, optionally. It can connect to a Supabase (PostgreSQL) database with row-level security for multi-user use. That happens only if someone deliberately adds a connection string to a `.env` file. Setting `COUNSELGRID_BACKEND=sqlite` in `.env` guarantees local mode. |

**Recommendations for your IT team**

- Keep the folder on an encrypted drive (BitLocker on Windows, FileVault on macOS), as you would any confidential file.
- If you try the tool with real names, start with an empty database. Before the first launch, copy `.env.example` to `.env` and set `COUNSELGRID_SEED_DEMO=false`. In this prototype, panel firms are loaded through SQL by IT (see `sql/seed.sql` for the format) rather than through a screen.
- Treat this as an evaluation build. Run it through your normal software and information-security review before using it with live client information.

---

## Feedback we would value

This was built as a learning project about corporate legal operations. If you have a few minutes, comments on any of these would help most:

1. Does the conflict gate reflect how your firm screens new matters? What does it miss?
2. Is the 100-point ranking fair to the way clients actually choose outside counsel?
3. Which report would your operations team want that is not here?

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Python is required" | Install Python (Step 1), then run the launcher again. |
| The browser did not open | Open **http://localhost:8501** manually. |
| "Port 8501 is already in use" | CounselGrid is already running in another window. Close that window or use the open browser tab. |
| Start over with fresh demo data | Close the app, delete the `data` folder and launch again. |
