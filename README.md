# Follow-for-Follow DM Bot

Reference Instagram pages ke **active** followers ko roz, limit ke andar, DM bhejne wala bot.
Control Telegram se. Phone par ek tap me chalu.

---

## Pehle ye padho

1. **Ye Instagram ke Terms ke against hai.** Cold DM ka koi official API nahi hai, isliye ye bot
   private API use karta hai.
2. **Risk real hai.** Followers main account par chahiye to DM bhi wahi se jane padenge, isme
   shortcut nahi. Chalane se pehle **2FA on karo** aur email/phone verified rakho.
3. **Limits mat badhao.** Bot khud aapke account ka limit dhoond leta hai, uspar bharosa karo.
4. **Bot ke saath account normal bhi use karte raho.** Reels post karo, comments ka reply do,
   stories dekho. Sirf DM bhejne wala account Instagram ko turant bot lagta hai. Ye sabse bada
   protection hai, koi setting nahi.

---

## Ye khud limit dhoondta hai

Instagram ka ek chhupa hua cap hota hai: **"24 ghante me kitne naye logon se chat shuru kar
sakte ho"**. Har account ka alag hota hai, aur Instagram batata nahi.

Cap lagne par ye error aata hai:

```
error_code 1545119
There is a limit to the number of new conversations you can start
every 24 hours with people who don't follow you
```

**Ye ban nahi hai.** Bot isko pehchanta hai, us number ko yaad rakh leta hai, aur aage se uske
2 neeche rukta hai. Har 5 din me 2 aur try karke dekhta hai ki limit badhi ya nahi. Matlab bot
aapke account ka sahi speed khud dhoond leta hai.

Ye ginti **rolling 24 ghante** ki hoti hai, calendar din ki nahi. Kal raat 11 baje 12 DM bheje
to aaj subah 11 baje wo abhi bhi Instagram ki ginti me hain. Bot bhi isi tarah ginta hai,
isliye "naya din" samajh ke dobara full speed nahi chalta.

`/status` me dikh jayega: `Aapke account ka Instagram limit 12 ke aas paas mila tha.`

---

## Speed

`.env` me `ACCOUNT_MODE` set karo:

| | `new` | `warm` |
|---|---|---|
| Kiske liye | naya ya thanda account | 3+ month purana, roz post, real engagement |
| Din 1-2 | 5 | 10 |
| Din 3-5 | 5 | 20 |
| Din 6-9 | 10 | 30 |
| Aage | 22-28 | 33-40 |
| Per hour | 4 | 8 |
| DM ke beech gap | 150-600 sec | 100-360 sec |

Ye upper limit hai. Neeche wala asli cap hamesha jeetta hai.

Baaki: sirf 11 baje se 10 baje raat tak, har 6-7 din me ek rest day, follow-back roz 25 tak,
ek bande ko dobara kabhi DM nahi.

---

## Bot kaise chunta hai kisko DM kare

Targets reference page ki **following** list se aate hain, yaani wo log jinko wo page follow
karta hai. `.env` me `SCRAPE_SOURCE=followers` karke ulta bhi kar sakte ho.

Following list chhoti hoti hai (aksar kuch sau), followers list hazaron ki. Isliye following
use kar rahe ho to **10-15 reference pages zarur rakhna**, warna targets jaldi khatam ho jayenge.

Pehle sasta filter (koi API call nahi): private, verified, bina profile pic wale nikal do.

Phir har candidate par:

| Check | Kyun |
|---|---|
| 50k+ followers | celeb ya brand, reply nahi karega |
| 3000+ following | ye khud follow-bot hai |
| 3 se kam post | fake ya khali account |
| **Story lagi hai?** | **abhi zinda hai, aaj active hai** |
| Story nahi to last post 21 din se purani? | dead account, chhod do |

Story wala check hi wo cheez hai jo bot accounts ko chhanta hai. Isse DM kam jayenge par
sahi logon ko jayenge. Tez chahiye aur quality ki parwah nahi to `.env` me
`CHECK_ACTIVITY=false`.

---

## Phone par setup

Ek baar ka kaam. Uske baad hamesha ke liye **ek tap**.

### Step 1: F-Droid se 3 apps

Play Store wala Termux purana aur toota hua hai. [F-Droid](https://f-droid.org/) install
karke usme se ye teen lo:

| App | Kaam |
|---|---|
| **Termux** | Linux terminal, isme bot chalta hai |
| **Termux:Widget** | Home screen wala one-tap button |
| **Termux:Boot** | Phone restart hone par apne aap chalu |

Teeno install karne ke baad **Termux:Boot ko ek baar khol lena** (bina khole ye kaam
nahi karta). Khulte hi khali screen dikhegi, wahi sahi hai, band kar do.

### Step 2: Telegram bot banao

- `@BotFather` → `/newbot` → naam do → **token copy karo**
- `@userinfobot` → `/start` → **apna numeric id copy karo**

Dono kahin note kar lo, abhi chahiye honge.

### Step 3: Termux me setup chalao

Termux kholo aur bas ye **ek line** paste karo:

```bash
pkg install -y git && git clone <apka-repo-url> ~/ff-bot && cd ~/ff-bot && bash setup.sh
```

Ye sab kuch khud kar dega: packages, python libraries, widget shortcut, boot script, `.env`.

**Ye script jitni baar chaho chala sakte ho.** Har step pehle check karta hai ki kaam ho
chuka hai ya nahi. Jo ho gaya wo dobara nahi hoga, sirf jo bacha hai wahi hoga:

```bash
bash setup.sh
```

Beech me build ruk jaye, phone hang ho jaye, ya net chala jaye to bas yahi dobara chala do.
Pehle ka kaam bacha rehta hai.

**Folder `~/ff-bot` me hi rakhna, Downloads ya SD card me nahi.** Shared storage par
SQLite ka file locking bharosemand nahi hai aur database kharab ho sakta hai. Script
wahan chalne se mana kar degi.

Pehli baar **20-40 minute** lag sakte hain. Android ke liye pydantic ki ready wheel nahi
banti, isliye wo Rust me compile hota hai. Screen band mat karna, charger laga lena.
Ek baar ban jaye to cache me reh jata hai, dobara kabhi nahi banega.

### Step 4: `.env` bharo

```bash
nano ~/ff-bot/.env
```

Ye 4 zaruri hain:

```
IG_USERNAME=aapka_username
IG_PASSWORD=aapka_password
TELEGRAM_TOKEN=BotFather wala token
TELEGRAM_OWNER_ID=aapka numeric id
```

Save karne ka tarika: `Ctrl+O` → Enter → `Ctrl+X`.
(Termux me Ctrl volume-down button se bhi milta hai.)

Pehli baar `DRY_RUN=true` hi rehne do.

### Step 5: Battery permission

**Ye sabse zyada log yahin bhool jaate hain aur phir bot beech me band ho jata hai.**

Phone Settings → Apps → **Termux** → Battery → **Unrestricted** (ya "No restrictions").

MIUI/Realme/Oppo/Vivo par ek aur cheez: Recent apps kholo → Termux card ko neeche kheech
kar **lock** kar do, taki "clear all" se na mare.

### Step 6: Home screen par button

Home screen par khali jagah der tak dabao → **Widgets** → **Termux:Widget** dhoondo →
home screen par drag karo.

Widget me **ff-bot** naam dikhega. **Bas wahi ek tap.**

---

## Roz kaise use karna hai

```
Shaam ko widget dabao
   -> Telegram par message aayega ki chalu ho gaya
   -> phone jeb me daal do, apna kaam karo
   -> 3 ghante baad bot khud band, Telegram par summary
```

Bas itna hi. Terminal me kuch type nahi karna.

Bot do surat me khud band hota hai: **3 ghante kaam ke pure hone par**, ya **raat 10 baje
active window khatam hone par** (jo pehle aa jaye). Dusra isliye ki raat bhar khali chalte
rehna phone ki battery kha jata hai.

**Beech me band karna ho:** Telegram par `/stop`.

**Best time: shaam 6 se 10.** Tab log online hote hain aur stories bhi zyada lagi hoti hain,
to activity filter ko zyada acche log milte hain.

### Sab kuch yaad rehta hai

Bot band karne par kuch nahi khota. Sab kuch `data/` folder me save rehta hai:

| | |
|---|---|
| Instagram session | dobara login nahi hoga, OTP nahi maangega |
| Kisko DM ja chuka | kisi ko dobara DM nahi jayega |
| Queue | jahan chhoda tha wahin se aage |
| Day counter aur warmup | band rakhne se warmup reset nahi hota |
| Discovered cap | account ka seekha hua limit yaad rehta hai |
| Follow-back list | koi follower miss nahi hoga |

### Phone restart ho gaya to

Kuch nahi karna. Termux:Boot bot ko apne aap chalu kar dega, 30 second baad, aur wahin se
kaam shuru hoga jahan chhoda tha.

Agar restart aadhi raat ko hua to bot chalu to ho jayega par kaam nahi karega, kyunki active
window (11 baje se 10 baje raat) ke bahar hai. `RUN_HOURS` ka 3 ghante ka counter bhi tabhi
chalta hai jab bot sach me kaam kar raha ho, to raat ka waqt zaya nahi hota.

### Do baar widget daba diya to

Kuch nahi bigdega. Dusra process dekh lega ki bot pehle se chal raha hai aur khud band ho
jayega. Do bot ek saath chalna sabse khatarnak cheez hoti, isliye ye guard laga hai.

---

## Telegram commands

| Command | Kaam |
|---|---|
| `/status` | Aaj kitne gaye, kitne bache, account ka limit |
| `/refs` | Reference pages ki list |
| `/addref username` | Naye page add (ek saath kai bhi) |
| `/delref username` | Page hatao |
| `/msg text` | Message set karo |
| `/preview` | Message kaisa dikhega |
| `/queue` | Kitne log line me hain |
| `/report` | 7 din ka summary |
| `/pause` `/resume` | Rok do / chalu karo |
| `/stop` | Bot poora band |

### Message

```
/msg Hey {name}, follow for follow? | Hi {name}, f4f? | {name} follow for follow karein?
```

`|` se alag karo, bot randomly ek chunega. **Ye zaruri hai.** Bilkul same text baar baar
bhejna Instagram ka sabse aasan spam signal hai.

`{name}` me bande ka pehla naam aayega. Naam na ho to username se guess kar lega
(`priya_23` → `Priya`).

---

## Best practices

**Reference pages kaise chuno**

- Aapke niche ke chhote-medium creators (5k-50k). Bade pages ke followers zyadatar dead hote hain.
- 10-15 pages rakho, sirf 1-2 nahi. Ek hi page se sabko DM jayega to pattern ban jata hai.
- Aisa page jiske followers **aapke jaise log** hon, warna follow karke unfollow kar denge.

**Roz**

- Bot chalane se pehle ya baad me khud 10 minute Instagram normal use karo
- Jo reply kare uska jawab **khud** do, wo asli connection banta hai
- Hafte me ek din bot bilkul mat chalao (bot khud bhi rest day leta hai)

**Kya nahi karna**

- Limits badhana. Cap discovery ko kaam karne do.
- Message me link daalna. Link + cold DM = double spam signal.
- Ek din me kai baar chalu band karna. Ek session, phir chhod do.
- Do account ek saath chalana ek hi phone se.

---

## Test

Code badalne ke baad ye chalao. Nakli Instagram par poora bot 30 din tak chalta hai
aur check karta hai ki koi limit toot to nahi rahi:

```bash
python tests/simulate.py
```

Ye asli Instagram ko chhuta bhi nahi. 8 scenario check hote hain: normal chalna, cap
discovery, sab targets dead, spam block, login challenge, follow-back, baar baar restart,
aur 30 din ka lamba run.

---

## Account badalna

Naye account par jaane se pehle **reset zaruri hai**:

```bash
python scripts/reset.py
```

Backup bana ke purana data hata dega. Warna purane account ka cap aur followers naye par
lag jayenge, aur warmup skip ho jayega.

---

## Jab kuch galat ho

| Telegram par ye aaye | Matlab | Kya karo |
|---|---|---|
| "Aaj ke liye Instagram ne rok diya" | roz ka naya-chat cap | Kuch nahi. Kal apne aap chalu ho jayega, aur kal ka target kam kar diya gaya hai. |
| "Instagram ne rok diya hai" (48 ghante) | asli spam block | 2 din bot mat chalao. App se normal use karo. Phir `/resume`. |
| "Instagram login verify maang raha hai" | challenge | App kholo, confirm karo, phir `/resume` |
| "Targets khatam ho gaye" | queue khali | `/addref` se naye pages daalo |
| Bot chup ho gaya | Android ne maar diya | Battery Unrestricted check karo |
| "Bot pehle se chal raha hai" | do baar widget daba diya | Kuch nahi, ye sahi hai |

Detail me dekhna ho to `data/ff.log` file me poora record hota hai.
Restart ke baad wala log `data/boot.log` me.

**Widget me ff-bot nahi dikh raha** → Termux:Widget install hai? Setup script chalaya tha?
Dobara chalao: `cd ~/ff-bot && bash scripts/install-termux.sh`

**Restart par apne aap chalu nahi hua** → Termux:Boot app ko ek baar khol ke band karo,
phir phone restart karke dekho. Bina khole ye kaam nahi karta.

**Bot band karke phir chalaya, wapas warmup Day 1 par aa gaya** → aapne `data/` folder
delete kar diya hoga. Wo folder hi bot ki yaadash hai, use mat chhedna.

Setup ki lagbhag har dikkat ka ek hi jawab hai: **`bash setup.sh` dobara chala do.**
Wo dekh lega ki kya bacha hai. Neeche wajah samajhne ke liye:

| Error | Wajah | Fix |
|---|---|---|
| `Installing pip is forbidden` | Termux apne pip ko protect karta hai | `bash setup.sh` (script ab pip upgrade nahi karti) |
| `Failed to determine Android API level` | Rust ko Android version nahi mila | `bash setup.sh` (script ab set karti hai) |
| `headers or library files could not be found for jpeg` | Pillow source se ban raha tha | `bash setup.sh` (ab `python-pillow` pkg se aata hai, banta hi nahi) |
| Build beech me mara, phone hang | RAM kam padi | `CARGO_BUILD_JOBS=1 bash setup.sh` |

Ek baar bana hua pydantic wheel cache me reh jata hai. Isliye baar baar retry karne par
bhi wo 20-40 min dobara nahi lagta.

**`RUKO. Ye folder shared storage me hai`** → repo ko `~/ff-bot` me le jao:
`cp -r <purana folder> ~/ff-bot && cd ~/ff-bot && bash scripts/install-termux.sh`

---

## Windows par (fallback)

```bash
pip install -r requirements.txt
```

`.env` bharo, `run.bat` double click. Agar `pip install` pydantic-core compile karne lage to
pehle `pip install "pydantic>=2.12"` chalao.

---

## Files

```
ff_bot/
  config.py      settings, profiles, limits
  db.py          SQLite
  ig.py          Instagram engine + error pehchan
  scraper.py     targets nikalna + quality/activity filter
  scheduler.py   quota, rest day, cap discovery
  sender.py      DM bhejna
  followback.py  follow back
  telegram.py    control panel
  worker.py      background loop
  copy.py        saare messages
scripts/
  install-termux.sh   ek baar ka phone setup
  ff-bot.sh           one-tap launcher
  reset.py            account badalne par
data/
  ff.db, session.json, ff.log
```

`.env` aur `data/` kabhi commit mat karna. `.gitignore` me pehle se hain.
