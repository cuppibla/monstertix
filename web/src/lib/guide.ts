/** The core course. Detailed implementation reading stays in content/steps. */
export type GuideAction = {
  title: string; text: string; button: string; expect: string; prompt?: string;
};
export type Guide = {
  number: number; title: string; minutes: string; intro: string; boundary: string;
  phases: {label: string; actions: string[]}[]; concept: string; explanation: string;
  source: string; highlight: string; actions: Record<string, GuideAction>;
};
const request = "Get me and Sam two tickets to the Amsterdam show.";
export const guides: Record<string, Guide> = {
  meet: {
    number: 1, title: "One night out. Two tickets.", minutes: "3–5 min",
    intro: "You and Sam want to see The Midnight Signal in Amsterdam. Sam can only make the weekend, and you prefer to avoid the upper bowl. You cannot spend the whole evening watching a ticket page.",
    boundary: "First, check the rig. No booking starts here.",
    phases: [{label: "Check the environment", actions: ["prepare"]}],
    concept: "A long-running task can outlive the process doing it.",
    explanation: "Getting tickets may take several runs, a wait and a restart. The agent needs somewhere to save progress and something to wake it later. The venue keeps moving while the agent is stopped.",
    source: "agent/concert/agent.py", highlight: "^root_agent = Agent\\(",
    actions: {},
  },
  wake: {
    number: 2, title: "Who starts the next check?", minutes: "8–10 min",
    intro: "Ask the agent to keep an eye on the Amsterdam show. It can check now. Once that answer ends, an external request has to start the next run.",
    boundary: "A fresh availability-check session. This chapter does not buy tickets.",
    phases: [
      {label: "Ask once", actions: ["prepare", "request"]},
      {label: "Let the clock call", actions: ["clock", "waiting", "inspect"]},
    ],
    concept: "Trigger → Runner → agent",
    explanation: "The prompt is read during an invocation. A clock supplies the next request; the Runner then calls the model and tools again. A server can stay up while no agent invocation is running.",
    source: "agent/concert/agent.py", highlight: "^root_agent = Agent\\(|instruction=|tools=",
    actions: {
      request: {title: "Ask it to keep watching. Then stop typing.",
        text: "Send one request. Read its answer and notice that the invocation count then stops changing.",
        button: "Send this request", prompt: "Keep an eye on the Amsterdam Saturday show for me and Sam.",
        expect: "One invocation finishes. No new invocation starts just because the page stays open."},
      clock: {title: "Let a timer start the next run.", text: "Schedule one check in 10 seconds. Watch the timer source and the new invocation together.",
        button: "Check again in 10 seconds", expect: "An external timer fires; the same session gains another invocation."},
    },
  },
  remember: {
    number: 3, title: "What carries into the next conversation?", minutes: "12–15 min",
    intro: "Sam's weekend rule helps the agent pick Saturday. Now save one more preference, then open one new session and see exactly what it can read.",
    boundary: "A fresh memory experiment. You will change session once; the two IDs stay visible in the evidence.",
    phases: [
      {label: "Read one run", actions: ["prepare", "request"]},
      {label: "Save a preference", actions: ["remember"]},
      {label: "Try a new session", actions: ["new-session", "inspect"]},
    ],
    concept: "Session DB and Memory Service have different jobs.",
    explanation: "The Session DB holds this conversation's events and task state. The Memory Service holds selected facts for later tasks to recall. Both persist, but opening a new session does not continue the old task.",
    source: "agent/concert/memory.py", highlight: "^class MarkdownMemoryService|^async def recall|^async def remember|async def search_memory",
    actions: {
      request: {title: "Find the Saturday choice in one trace.", text: "Send the familiar request. Then open the evidence below: what did recall return, and which show did get_seatmap use?",
        button: "Send this request", prompt: request, expect: "recall and get_seatmap are recorded in this session. No purchase is made."},
      remember: {title: "Keep one fact for next time.", text: "The page compares the memory file before and after. A friendly 'noted' is not enough: look for a real remember call and a new line.",
        button: "Save this preference", prompt: "Remember this for next time — we always want aisle seats.",
        expect: "The Memory Service writes a new aisle preference."},
      "new-session": {title: "Ask again in one new session.", text: "This creates session B and sends the same request. Compare its recall response with session A; you do not need to switch between several dropdowns.",
        button: "New session + ask again", prompt: request,
        expect: "B recalls the saved preference. A's conversation and task state still belong to A."},
    },
  },
  resume: {
    number: 4, title: "Kill the process. Keep your place.", minutes: "12–15 min",
    intro: "Remembering a preference is useful. Now we need to remember unfinished work: which show we picked and where we are in its queue. Pause the task, kill its process, then bring that same task back. Stop before buying.",
    boundary: "A new workflow experiment. Keep this session from the first queue ticket through the restart.",
    phases: [
      {label: "Join and pause", actions: ["prepare", "request"]},
      {label: "Kill the process", actions: ["kill"]},
      {label: "Restart and resume", actions: ["restart", "resume", "inspect"]},
    ],
    concept: "Completed nodes reuse records. The waiting node checks again.",
    explanation: "The show choice and queue ticket already have completed records. Resume reuses those outputs. check_front stopped on a wait, so it queries the venue again. The result is ready_to_buy, with zero orders.",
    source: "agent/concert/nightly.py", highlight: "^@node\\(|^def check_front|^def queue_up|^def ready_to_buy",
    actions: {
      request: {title: "Let the task stop itself in the queue.", text: "Send the request once. check_front pauses the invocation when the ticket is not yet at the front.",
        button: "Start the task", prompt: request, expect: "One queue ticket and a pending queue:wait. No order."},
      kill: {title: "Stop the actual agent process.", text: "After this click, pause and watch the venue. The queue position can still move while the agent process is gone.",
        button: "Kill agent", expect: "Agent stopped; the same queue ticket still exists."},
      restart: {title: "Bring the process back.", text: "The service restarts with the same Session DB. It does not buy or create a new task.",
        button: "Restart agent", expect: "The original session is still paused on the same queue wait."},
      resume: {title: "Continue the original task.", text: "This moves only this ticket to the front, then answers its queue:wait. Open the recorded events to distinguish graph traversal from node execution.",
        button: "Move to the front + resume", expect: "Same session, same ticket, ready_to_buy, zero orders."},
    },
  },
  buy: {
    number: 5, title: "Buy the one order you agreed to.", minutes: "15–18 min",
    intro: "Seats can sell out while you wait. An order can also be committed before the venue returns an error. See authorization, a guard and a safe retry in one purchase.",
    boundary: "A new purchase task needs your own authorization. From that answer to the final receipt, keep this same session.",
    phases: [
      {label: "You set the limit", actions: ["prepare", "request", "answer"]},
      {label: "Prepare the faults", actions: ["scenario"]},
      {label: "Resume and inspect", actions: ["resume", "inspect"]},
    ],
    concept: "One purchase, three protections.",
    explanation: "Your authorization sets the quantity and price limit. The guard checks the live world before a purchase. The Idempotency-Key lets a retry of that same operation retrieve the original order.",
    source: "agent/concert/tools.py", highlight: "^def purchase\\(|key = hashlib|Idempotency-Key|while attempts|attempts.*idempotency_key",
    actions: {
      request: {title: "Start the task. It asks before spending.", text: "The workflow asks for the quantity and per-ticket limit, then reads them back. You answer both questions here; the page routes each answer to the correct pending event.",
        button: "Start the task", prompt: request, expect: "A question for you. No queue ticket or order until you confirm."},
      scenario: {title: "Prepare one changing-world scenario.", text: "This sells out section A for your selected show, arms a commit-then-503 failure, and moves your ticket to the front. It leaves the agent paused. Each operation must succeed before the next one runs.",
        button: "Prepare the three changes", expect: "A sold out · next purchase returns 503 after commit · your ticket at the front. Zero orders."},
      resume: {title: "Resume once. Read one result card.", text: "The guard should refuse the stale A plan. The agent can choose C. When the venue commits and returns 503, the tool retries automatically with the same key; you do not click Buy again.",
        button: "Resume this task", expect: "stale_plan · attempts: 2 · duplicate: true · one matching order."},
    },
  },
  cloud: {
    number: 6, title: "Let the cloud make the next call.", minutes: "8–10 min",
    intro: "You have already tried pausing, restarting and buying. Now watch a real cloud timer resume a waiting task without anyone typing into the page.",
    boundary: "Instructor demonstration in the core course. The cloud needs its own task and authorization; deploying does not move a local session.",
    phases: [
      {label: "Check the cloud task", actions: []},
      {label: "Trigger Scheduler", actions: []},
      {label: "Read the order", actions: []},
    ],
    concept: "Scheduler → Pub/Sub → service → saved task",
    explanation: "The deployment changes where the code and stores run. It still needs a caller, the correct session, an answered queue wait and a safe purchase. This lab's wake-up handler is a single-active-task example.",
    source: "agent/concert/agent.py", highlight: "^app = App|resumability_config=",
    actions: {},
  },
};
