# 📊 Indian Market Email Job — GitHub Actions (No PC Required)

Runs entirely on **GitHub's free servers**. Your PC can be off.
Sends BSE Sensex + top-15 gainers & losers to you and your friends
— 3× on trading days, once on holidays/weekends.

---

## 🚀 Setup (one-time, ~10 minutes)

### Step 1 — Create a GitHub account
Go to [github.com](https://github.com) and sign up (free).

---

### Step 2 — Create a new repository
1. Click **"New repository"** (top-right `+` button)
2. Name it: `indian-market-job`
3. Set visibility: **Private** (so your email stays safe)
4. Click **"Create repository"**

---

### Step 3 — Upload these files
Upload all 3 files to the root of your repo:
- `market_job.py`
- `requirements.txt`
- `.github/workflows/market_job.yml`  ← this folder structure matters!

**Easiest way to upload:**
1. In your repo, click **"Add file → Upload files"**
2. Upload `market_job.py` and `requirements.txt`
3. For the workflow file, click **"Add file → Create new file"**
4. In the filename box, type: `.github/workflows/market_job.yml`
5. Paste the contents of `market_job.yml` and commit.

---

### Step 4 — Add your Gmail App Password

First, generate a Gmail App Password:
1. Go to [myaccount.google.com](https://myaccount.google.com) → **Security**
2. Enable **2-Step Verification** (if not already)
3. Search for **"App Passwords"** → Create one → copy the 16-char code

Now add secrets to GitHub:
1. In your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"** and add these 3 secrets:

| Secret Name    | Value                                      |
|----------------|--------------------------------------------|
| `GMAIL_USER`   | `your_email@gmail.com`                     |
| `GMAIL_PASSWORD` | `abcd efgh ijkl mnop` (App Password)     |
| `RECIPIENTS`   | `you@gmail.com,friend1@gmail.com,friend2@gmail.com` |

> 💡 `RECIPIENTS` — comma-separated, no spaces around commas.

---

### Step 5 — Enable Actions & test

1. Go to **Actions** tab in your repo
2. If prompted, click **"I understand my workflows, enable them"**
3. Click **"Indian Market Email Job"** in the left sidebar
4. Click **"Run workflow"** → **"Run workflow"** (green button)
5. Watch it run — you should get an email within ~60 seconds! ✅

---

## 📅 Schedule

| Time (IST) | Time (UTC) | Slot      |
|------------|------------|-----------|
| 10:00      | 04:30      | Morning   |
| 13:00      | 07:30      | Afternoon |
| 15:15      | 09:45      | Closing   |

Runs **Monday–Friday only**. The script itself detects holidays via the
BSE calendar, so on festival days it sends "Market Closed" instead.

---

## 📧 What you'll receive

**On trading days (3 emails):**
```
Subject: 📊 [Morning] BSE Update — Sensex 82,345 (+0.45%) — 01 Apr 2025
```
Dark-themed HTML email with:
- Sensex value, change %, day high/low
- Top 15 gainers (green)
- Top 15 losers (red)

**On holidays / weekends (1 email):**
```
Subject: 🔴 BSE Market Closed — 14 Jan 2025
```
Shows the reason (e.g. "BSE Holiday — Makar Sankranti") and next upcoming holiday.

---

## 🔧 Customization

**Add more stocks to track:**
Go to repo → Settings → Secrets → add:
```
EXTRA_TICKERS = IRFC.NS,RAILVIKAS.NS,ZOMATO.NS
```

**Change number of gainers/losers (default 15):**
Add secret: `TOP_N = 10`

**Add/remove recipients:**
Edit the `RECIPIENTS` secret — comma-separated emails.

---

## 📊 Monitoring

- **Actions tab** → see every run, logs, pass/fail status
- GitHub emails you if a run fails
- Logs show Sensex value, number of stocks fetched, mail status

---

## ❓ FAQ

**Q: Is this really free?**
A: Yes. GitHub Actions gives 2,000 free minutes/month on private repos.
   Each run takes ~30 seconds × 3 runs × ~22 trading days = ~33 min/month.
   Well within free limits.

**Q: What if a run fails?**
A: GitHub will email you. Check the Actions tab for the error log.

**Q: Can I change the schedule?**
A: Edit `.github/workflows/market_job.yml` — change the `cron:` values.
   Use [crontab.guru](https://crontab.guru) to verify your cron expression.
   Remember: GitHub cron is always UTC.

**Q: Will it work on Diwali / Holi / Eid etc?**
A: Yes — the script uses the official BSE holiday calendar which knows
   all Indian market holidays. It will send "Market Closed" on those days.
