"""Saara user-facing text. Hinglish, chhota, seedha. Koi em dash nahi."""

WELCOME = (
    "Namaste. Main aapka follow-for-follow bot hoon.\n\n"
    "Kaam simple hai: aap reference pages doge, main unke followers me se "
    "acche accounts chunkar roz limit ke andar DM bhejunga.\n\n"
    "Neeche button dabao ya /help dekho."
)

HELP = (
    "Commands:\n"
    "/status - aaj ka hisaab\n"
    "/refs - reference pages ki list\n"
    "/addref username - naya page add\n"
    "/delref username - page hatao\n"
    "/msg text - message set karo\n"
    "/preview - message kaisa dikhega\n"
    "/queue - kitne log line me hain\n"
    "/report - 7 din ka summary\n"
    "/pause - rok do\n"
    "/resume - chalu karo\n"
    "/stop - bot poora band (battery bachane ke liye)\n\n"
    "Message me {name} likhoge to wahan banda ka naam aayega.\n"
    "Ek se zyada version chahiye to | se alag karo, main randomly chunuunga."
)

BTN_STATUS = "Aaj ka status"
BTN_QUEUE_LABEL = "Queue"
BTN_REFS = "Reference pages"
BTN_MSG = "Message set karo"
BTN_TOGGLE = "Start / Pause"
BTN_REPORT = "Report"

NOT_OWNER = "Ye bot aapke liye nahi hai."

DRY_RUN_ON = "Abhi DRY RUN mode on hai. Kuch actually send nahi hoga, sirf test."

REF_ADDED = "Add ho gaya: @{u}. Thodi der me iske followers scan karunga."
REF_EXISTS = "@{u} pehle se list me hai."
REF_DELETED = "Hata diya: @{u}"
REF_NOT_FOUND = "@{u} list me mila hi nahi."
REF_BAD = "Ye samajh nahi aaya: {u}\nSirf username do, poora link nahi."
REF_EMPTY = "Abhi koi reference page nahi hai.\nAdd karo aise: /addref username"
REF_USAGE = "Aise likho: /addref username"

MSG_SET = "Message set ho gaya:\n{t}"
MSG_USAGE = "Aise likho: /msg Hey {name}, follow for follow?"
MSG_NO_NAME = (
    "Note: message me {name} nahi hai, to sabko bilkul same text jayega. "
    "Chalega, par naam wala message zyada natural lagta hai."
)

PAUSED = "Rok diya. /resume se wapas chalu hoga."
RESUMED = "Chalu kar diya."
ALREADY_PAUSED = "Pehle se ruka hua hai."
ALREADY_RUNNING = "Pehle se chal raha hai."

QUEUE_INFO = "{n} log queue me hain. Roughly {days} din chal jayega."
QUEUE_EMPTY = "Targets khatam ho gaye. Naya reference page add karo:\n/addref username"
QUEUE_LOW = "Queue kam ho raha hai, sirf {n} bache. Ek do naye reference page add kar do."

STATUS_RUNNING = "Aaj {sent} DM gaye, {left} bache.\nNext DM {mins} min me.\nQueue me {queue} log hain."
STATUS_DONE = "Aaj ka kaam khatam. {sent} DM gaye.\nQueue me {queue} log hain. Kal phir."
STATUS_PAUSED = "Abhi ruka hua hai. /resume se chalu karo.\nAaj ab tak {sent} DM gaye."
STATUS_REST = "Aaj rest day hai. Account ko break dena zaruri hai, kal se normal."
STATUS_SLEEP = "Abhi active time nahi hai. {start} baje se {end} baje ke beech kaam hota hai."
STATUS_COOLDOWN = "Cooldown chal raha hai, {until} tak sab band hai."

WARMUP_NOTE = "Warmup chal raha hai. Day {day} hai, aaj ka target {quota} DM."
CAP_NOTE = "Aapke account ka Instagram limit {cap} ke aas paas mila tha. Aaj {target} try karunga."
STOPPING = "Band kar raha hoon. Widget se dobara chalu kar dena."

DAY_DONE = "Aaj ka kaam khatam. {ok} DM gaye, {fail} fail hue. {queue} log abhi queue me hain."
REST_DAY = "Aaj rest day hai, koi DM nahi jayega. Ye jaan bujh kar hai, account safe rehta hai."

DAILY_CAP = (
    "Aaj ke liye Instagram ne rok diya.\n\n"
    "{sent} DM ke baad usne kaha ki naye logon se itne hi chat shuru kar sakte ho. "
    "Ye ban nahi hai, roz ka apna limit hai.\n\n"
    "Ab se aaj ka target {cap} rakhunga. {until} se apne aap chalu ho jayega."
)

SESSION_OVER = (
    "{hours} ghante pure ho gaye, band kar raha hoon.\n"
    "Aaj total {sent} DM gaye. Phir chalana ho to widget dabao."
)

SESSION_WINDOW_OVER = (
    "Aaj ka time khatam, band kar raha hoon.\n"
    "Aaj total {sent} DM gaye. Kal widget daba dena."
)

CONFIG_BAD_HOURS = (
    "Dhyaan do: .env me ACTIVE_START_HOUR aur ACTIVE_END_HOUR galat hain, "
    "isliye bot kabhi kaam nahi karega. Start chhota aur end bada hona chahiye, "
    "jaise 11 aur 22."
)

DAILY_CAP_EARLY = (
    "Instagram ne aaj abhi se rok diya.\n\n"
    "Kal ke DM ab bhi uski 24 ghante ki ginti me hain, isliye aaj pehle hi message par "
    "limit lag gaya. Ye ban nahi hai.\n\n"
    "{until} se apne aap chalu ho jayega."
)

STATUS_CAP = "Aaj ka Instagram limit lag gaya hai. {until} se dobara chalu hoga."
STATUS_CAP24 = "Pichhle 24 ghante ka limit pura ho gaya. Thodi der me apne aap chalu hoga."

COOLDOWN_HIT = (
    "Instagram ne rok diya hai.\n\n"
    "{hours} ghante ke liye sab band kar diya hai. Tab tak app se normal use karo, "
    "scroll karo, story dekho. Isse trust wapas aata hai.\n\n"
    "Wajah: {reason}"
)
CHALLENGE = (
    "Instagram login verify maang raha hai.\n\n"
    "Phone me Instagram app kholo, jo confirm karne ko bole wo kar do. "
    "Phir mujhe /resume bhejo."
)
LOGIN_FAILED = "Instagram login nahi hua.\n\nWajah: {reason}\n\n.env me username password check karo."

FOLLOWBACK_DONE = "{n} logon ne follow kiya, sabko follow back kar diya."
FOLLOWBACK_SEEDED = (
    "Aapke abhi ke followers ki list bana li.\n"
    "Aaj follow-back kuch nahi karunga. Ab se jo naya follow karega, use kar dunga."
)

ALL_FILTERED = (
    "Queue me log hain par koi DM ke layak nahi mila. Zyadatar dead ya bot accounts hain.\n\n"
    "Thodi der baad dobara try karunga. Baar baar aisa ho to naye reference pages add karo, "
    "ya .env me CHECK_ACTIVITY=false karke filter dheela kar do."
)

REFS_DRY = (
    "Saare reference pages se log nikal chuke, ab kuch naya nahi mil raha.\n"
    "2-3 naye page add karo: /addref username"
)

REPORT_HEAD = "Last 7 din:"
REPORT_ROW = "{day}  {ok} gaye, {fail} fail"
REPORT_EMPTY = "Abhi koi data nahi hai. Ek do din chalne do."

PREVIEW = "Aise dikhega:\n\n{samples}"

ENV_MISSING = "Ye settings .env me missing hain: {keys}\nInke bina bot chal nahi sakta."

ALREADY_RUNNING_PROC = (
    "Bot pehle se chal raha hai (PID {pid}).\n"
    "Do bot ek saath chalana theek nahi, isliye ye band kar raha hoon.\n"
    "Status dekhna ho to Telegram par /status bhejo."
)

STARTED = "Bot chalu ho gaya. Day {day}, aaj ka target {quota} DM."
