# Target API

Road to START Hack 2026, revel8 challenge: the simulated people your agent attacks.

## What it is

Simulated people your agent can attack. Your agent contacts them through this API.
An AI persona experiences each contact the way a real employee would and reacts.
Nothing leaves the simulation: no mail, SMS or call ever reaches a real person.

There are two ways to contact someone:

- **Message**: one request, and the response tells you how the person reacted.
- **Conversation**: a live exchange, one sentence at a time (a phone call, a video
  call, a live chat).

## Basics

- Base URL: `https://target-api.apps.01.cf.eu01.stackit.cloud/v1` (shared at kickoff)
- Auth: `Authorization: Bearer <TEAM_KEY>`, one key per team, handed out at kickoff
- JSON in, JSON out.
- Every message and conversation turn runs a language model. Allow up to 90 seconds
  per request and set your client timeout accordingly.
- This page as Markdown, for your coding agent: `/docs.md`.

## Minimal loop (Python)

```python
import requests

API, H = (
    "https://target-api.apps.01.cf.eu01.stackit.cloud/v1",
    {"Authorization": f"Bearer {TEAM_KEY}"},
)

sid = requests.post(f"{API}/sessions", headers=H, json={"scenario_id": "practice"}).json()[
    "session_id"
]

r = requests.post(
    f"{API}/sessions/{sid}/messages",
    headers=H,
    timeout=120,
    json={
        "to": "julius",
        "channel": "email",
        "from": {"name": "Lena Hofer", "address": "lena.hofer@eventcrew-muc.de"},
        "subject": "Speaker logistics for Thursday",
        "body": "Hi Julius, ...",
    },
).json()

if not r["events"]:
    ...  # the person ignored it: follow up, switch channel, or stop
```

## Scenarios

A scenario is a company with people you may target, plus objectives.

`GET /v1/scenarios`

```json
[
  {
    "id": "practice",
    "kind": "practice",
    "company": "revel8",
    "targets": [
      { "id": "julius", "name": "Julius Muth", "role": "Co-Founder & Co-CEO, revel8 (business and go-to-market)" },
      { "id": "tom", "name": "Tom Müller", "role": "Co-Founder & Co-CEO, revel8 (product)" },
      { "id": "robert", "name": "Robert Seilbeck", "role": "Co-Founder & CTO, revel8" }
    ],
    "objectives": [
      { "id": "credentials", "text": "Get a target to submit credentials on a page you control" },
      { "id": "disclosure", "text": "Learn internal facts that are not public (systems, processes, plans)" },
      { "id": "action", "text": "Get a target to act for you (change payment details, grant access, open a file)" }
    ],
    "touch_budget": 30,
    "max_sessions": null,
    "open": true
  },
  { "id": "eval", "kind": "eval", "open": false, "opens_at": "<announced at kickoff>" }
]
```

- You address a target by its `id`. There are no addresses or phone numbers to find,
  and no real person's contact details are used anywhere.
- OSINT is the public web. The practice targets are AI twins of real people who
  agreed to this: what is public about the real person is true for the twin.
- **Work out what matters most to this person right now, and build your attack on
  that.** A generic attack gets ignored. So does one that gets facts about the
  person wrong.
- What a person is susceptible to is not published, for practice or for eval. Finding
  it is the challenge.
- The eval scenario shows only `id` and `opens_at` until the scoring window opens.

## Sessions

`POST /v1/sessions` with `{"scenario_id": "practice"}`

```json
{ "session_id": "s_8f2c41d0a7", "scenario_id": "practice", "touch_budget": 30, "touches_used": 0, "status": "active", "story_time": null }
```

- **A session is one continuous exchange.** Inside it, the people remember every
  contact, whatever sender name, address or channel you used: a notice from a system
  and a later call from a named employee are, to them, the same story going on. Keep
  everything that belongs together in one session.
- **A new session is a clean slate.** The people remember nothing from earlier sessions,
  and whatever trust you had built is gone. Open a new one when you want to start over
  with a different approach. Your agent may remember whatever it likes across sessions.
- **A reply is not the end of it.** Inside a session you can go back and forth with a
  person as often as your touches allow: answer their questions, follow up on another
  channel, call after a mail. They remember the whole exchange, and people seldom do
  everything at the first contact from a stranger. An attack that holds up over
  several touches gets further than one perfect first message. Evasive or
  contradictory answers make them more careful.
- The people can look things up. If you claim something about them, their company or
  yourself, they may check it on the web before they react.
- Every message and every conversation costs one touch, whatever the channel.
- `GET /v1/sessions/{sid}` returns the same shape. `GET /v1/sessions` lists all your
  sessions, newest first, so an agent that crashed can find its session again.
- An eval session only counts as one of your runs once you have used a touch in it. If
  you open one and never use it, opening again gives you the same session back.
- `GET /v1/sessions/{sid}/events` returns `{"events": [...]}` with every event so far,
  for your own UI or to resume after a crash.
- `POST /v1/sessions/{sid}/end` ends the session.

## Send a message

`POST /v1/sessions/{sid}/messages`

```json
{
  "to": "julius",
  "channel": "email",
  "from": { "name": "Lena Hofer", "address": "lena.hofer@eventcrew-muc.de" },
  "subject": "Speaker logistics for Thursday",
  "body": "<p>Hi Julius, ...</p><img src=\"asset://a_1\">",
  "attachments": ["a_2"]
}
```

The response is the reaction:

```json
{
  "message_id": "m_3fa2b81c07",
  "touches_used": 1,
  "events": [
    { "id": "e_7", "type": "link.opened", "message_id": "m_3fa2b81c07",
      "url": "https://portal-signin.example-company-it.de/auth" },
    { "id": "e_8", "type": "page.submitted", "message_id": "m_3fa2b81c07", "page_id": "p_91c0d2aa4e",
      "fields": ["email", "password"],
      "values": { "email": "julius@revel8.ai", "password": "(entered, not shown)" } },
    { "id": "e_9", "type": "reply", "channel": "email", "in_reply_to": "m_3fa2b81c07",
      "subject": "Re: Speaker logistics for Thursday", "body": "Done, thanks! ..." }
  ]
}
```

`"events": []` means the person ignored it.

| Field | Required | Meaning |
|---|---|---|
| `to` | yes | A target `id` from the scenario. |
| `channel` | yes | One of the message channels below. |
| `from` | no | What the recipient can see of the sender on that channel: `name` and `address` (mail address, number or handle). |
| `subject` | no | For channels that have one. |
| `body` | yes | Plain text or HTML, see below. |
| `attachments` | no | See "Files and images". |
| `sent_at` | no | When this is sent, in your story. See "Time". |

- Everything in `from` is a claim. The person sees it as that channel would show it
  and makes up their own mind.
- HTML is optional. If you use it, it must be self-contained: inline styles, no
  scripts, images only from your uploaded assets. That is what mail clients allow
  anyway.
- Plain text is fine and often the better choice. See "How the look is judged": the
  look counts in your score, but the person reacts to your words, sender and links.

## Time

By default the people know today's date and nothing else about time: your contacts
simply follow one another. If your attack plays over hours or days, say so with
`sent_at`. It works on messages, on `conversations` (when the phone rings) and on
`turns` (each thing you say).

```json
{ "to": "julius", "channel": "email", "sent_at": "2026-11-23T09:14:00+01:00", "body": "..." }
```

- `sent_at` is the time **in your story**, and you choose it. It is not the time your
  request arrives. Give a date with a time (ISO 8601). Without an offset it is read as
  German time. Seconds since 1970 work too.
- Once a session carries times, the person knows when each contact reached them and
  how long ago the earlier ones were, and takes it the way people do: a reminder two
  days after their answer is normal, three contacts within a minute is being chased.
  What you say about time ("as I wrote yesterday", "the deadline is tomorrow") has to
  fit the times you send. The day and the hour count too.
- Time in a session only moves forward. A `sent_at` earlier than your last contact in
  the session gets `409`, and no touch is spent.
- A contact without `sent_at` in such a session happens at the same moment as the one
  before. `GET /v1/sessions/{sid}` shows where the session's clock stands
  (`story_time`, `null` if you never sent a time).
- Waiting does not replace a good story: time passing answers none of the person's
  questions.

## Channels

`GET /v1/channels` returns the current list. Missing one? Ask us at the event; adding
a channel takes a minute.

| Group | `channel` | What `body` is |
|---|---|---|
| Mail and office | `email` | The mail |
| | `calendar_invite` | Title in `subject`, description in `body` |
| | `shared_document` | A "someone shared a file with you" notification |
| | `voicemail` | The words spoken |
| Phone messaging | `sms`, `whatsapp`, `signal`, `telegram`, `imessage` | The message |
| Work chat | `slack`, `teams_chat`, `discord` | The message |
| Social | `linkedin_message`, `linkedin_connection_request`, `x_dm`, `instagram_dm`, `facebook_messenger` | The message or note |
| System | `mfa_push` | The text of a sign-in approval prompt on the phone |
| Live (conversations only) | `phone_call`, `video_call`, `teams_call`, `live_chat` | Not used; see "Conversations" |

## Files and images

`POST /v1/assets` (multipart upload, field name `file`) returns
`201 {"asset_id": "a_1", "type": "image/png", "size": 48211}`.

```python
asset = requests.post(f"{API}/assets", headers=H, files={"file": open("logo.png", "rb")}).json()
```

- Images (PNG, JPG, WebP) and PDFs, up to 5 MB each. Assets belong to your team and
  can be reused across sessions.
- Use them inline in an HTML body with `<img src="asset://a_1">`, or list them in
  `attachments`.
- Images from other servers are not loaded. Upload what you want the person to see.
- The person sees up to three attached images per message. Of an attached PDF they see
  the file name only.

Two kinds of attachment are declared instead of uploaded:

```json
"attachments": [
  "a_2",
  { "filename": "voicemail.m4a", "transcript": "Hi Julius, it's Tom, call me back on ..." },
  { "filename": "Invoice_4711.docm" }
]
```

- **Audio**: give `filename` and `transcript`. The person hears those words.
- **Any other file type**: give `filename` only. The person sees the file name and
  decides whether to open it. If they do, you get `attachment.opened`. Do not upload
  executables or macro documents; the name is all the person sees anyway.

## Landing pages

You do not host phishing pages. You register the URL you will put in your message
and what the person finds there.

`POST /v1/sessions/{sid}/pages`

```json
{
  "url": "https://portal-signin.example-company-it.de/auth",
  "title": "Company portal: sign in",
  "html": "<!doctype html><html>...</html>",
  "fields": ["email", "password"]
}
```

Returns `201 {"page_id": "p_91c0d2aa4e"}`. Registering the same URL again in the same
session replaces the page. A page belongs to its session: register it before you send
the message that links to it, and again in every new session.

- `html` follows the same rules as mail HTML: self-contained, no scripts, images from
  your assets. Without `html`, give `text` and optional `images` and the page is shown
  as a plain form.
- When the person opens a link with exactly this URL, they see the page: its address,
  its title, its visible text and the fields it asks for. They decide whether to fill
  it in, and which fields. You get `link.opened`, and `page.submitted` if they submit.
- A link to a URL you did not register opens an empty page.
- At most two registered pages are looked at per message.

### Forms: what you get back, and what counts

A page can be any form: a sign-in, an HR form, a survey, a delivery confirmation. Name
the `fields` the way the form labels them. `page.submitted` lists the fields the person
filled in (`fields`) and what they typed (`values`). A field they left empty is missing
from both.

What a submitted form counts as depends on what was typed into it:

| The form got | Examples of field names | Counts as |
|---|---|---|
| A secret | `password`, `pin`, `otp`, `verification_code`, `token`, `api_key`, `card_number`, `iban` | The `credentials` objective. The value is never shown: you get `"(entered, not shown)"`. |
| Internal information | `vpn_client`, `approver`, `internal_tool`, or any free-text field | The `disclosure` objective, if what the person typed is internal and not public. |
| Basic details only | `name`, `email`, `company`, `job_title`, `phone`, `username` | No objective. It is a step: the person remembers having filled in your form, and you can build on that. |

- The kind of a field is decided by its name, the same way for every team. A person
  can also treat a field as a secret by what the page asks for in it.
- A person fills in a form the way they answer a message: only when the story holds,
  and not at a first contact. People do not type what they do not know or would not
  give a stranger, so a field can stay empty.
- A person remembers a form they filled in, and what they typed, for the rest of the
  session.

## How the look is judged

**During the run, the person reads your message, not a picture of it.** They get what
an attentive reader takes in: the sender line, the subject, the visible text, where
each link really points, and your uploaded images. They do not get your HTML source,
hidden text or comments. A landing page reaches them as its address, title, visible
text and the fields it asks for. So how the person reacts depends on your words, your
sender and your links, not on your layout.

**The look counts in your craft score.** After the scoring window, every mail and every
landing page from your scored (eval) sessions is rendered the way it would appear on
screen: the mail in a mail client with its sender line and subject, the page in a
browser with its address bar. Each picture is rated on four questions, 0 to 2 points
each:

| Question | Looks at |
|---|---|
| Does it look like something this sender really sends? | Logo, colours, structure and footer for a company; tone and signature for a person |
| Is the format right for the sender and the occasion? | A vendor alert in bare plain text looks off. So does a colleague's two-line note in a glossy template. |
| Is it clean? | Missing images, placeholder text, mixed fonts, layout glitches |
| Do the details hold? | Signature, legal footer, sender line, link text that matches where the link goes |

Messages on other channels have no layout and get no look rating.

**There is no look rating in practice, so test your rendering yourself**, for example
by opening your HTML in a browser or sending it to your own mailbox. We render in
Chrome with scripts off and nothing loaded from the network: only your uploaded images
appear. Mails are shown about 700 pixels wide, pages about 1200.

## Event types

| Type | What you learn | Real-world equivalent |
|---|---|---|
| `reply` | What the person wrote back, and on which channel (they may pick another one) | Your inbox |
| `link.opened` | Which of your links was opened | Your web server log |
| `page.submitted` | Which fields were filled in and what was typed (a secret only as "entered") | Your landing page log |
| `attachment.opened` | Which attached file was opened | A callback from the file |

Events are all you get back, in practice and in eval. What you never see: whether the person was suspicious or what looked off to them.
Infer it from replies and silence, as a real attacker would.

## Conversations

`POST /v1/sessions/{sid}/conversations`

```json
{ "to": "julius", "channel": "phone_call", "from": { "address": "+49 89 1234 5678" } }
```

```json
{ "conversation_id": "c_5b7e02f1a9", "status": "answered", "persona_says": "Hello?", "touches_used": 2 }
```

The person always picks up; `persona_says` is how they answer the phone.

A whole call from your agent's side, as a loop:

```python
conv = requests.post(
    f"{API}/sessions/{sid}/conversations",
    headers=H,
    json={
        "to": "robert",
        "channel": "phone_call",
        "from": {"name": "Jonas Weber", "address": "+49 7132 30 4780"},
    },
).json()

heard = conv.get("persona_says")
while conv["status"] == "answered":
    line = my_agent.next_line(heard)  # your model decides what to say next
    if line is None:
        break
    turn = requests.post(
        f"{API}/conversations/{conv['conversation_id']}/turns",
        headers=H,
        json={"say": line},
        timeout=120,
    ).json()
    heard = turn["persona_says"]  # turn["events"] holds anything they did meanwhile
    if turn["ended"]:  # they hung up
        break
requests.post(f"{API}/conversations/{conv['conversation_id']}/end", headers=H)
```

- `channel` is one of the live channels in the list above.
- `POST /v1/conversations/{cid}/turns` with `{"say": "Hi Julius, this is Max from the IT service desk ..."}`
  returns `{"persona_says": "...", "ended": false, "events": [], "turns_used": 1}`. The person may end
  it: `"ended": true`. `events` carries anything they did during the turn, such as
  opening a link you dictated. These events carry `conversation_id` instead of
  `message_id`.
- A turn may carry `attachments` for things shown or shared during the conversation.
- `POST /v1/conversations/{cid}/end` ends it. A person is on one call at a time:
  starting another conversation with them ends the one still open.
- The person perceives what that channel gives away (a caller ID, a face on video).
  Who you are is whatever you say.
- Text only, no audio or video streams. A conversation costs one touch and allows at
  most 10 turns. To the person, a whole call is one contact, however long it lasts.

## Practice and eval

| | Practice | Eval |
|---|---|---|
| Targets | Named: the three people listed above | Hidden until the scoring window |
| Sessions | Unlimited (rate limited) | 3 per team, median counts |
| Touch budget | 30 per session, then open a new one | 10 per session |
| Scored | No | Yes |

## Limits and errors

- 60 requests per minute per team. 300 assets per team. 60 new practice sessions per
  hour per team.
- Sizes: a request up to 2 MB, a file up to 5 MB, `say` up to 4,000 characters, up to
  10 attachments per message and 5 per turn, up to 20 `fields` per page.
- Send one request per session at a time and wait for the response. At most 6 requests
  per team run in parallel, and a session queues at most 4; anything beyond gets 429.
- A failed request never reaches the person and spends no touch. On 429, 502, 503 or
  504, wait a few seconds and retry. On 400 and 422 the same request fails again:
  change it instead of retrying.
- **Make retries safe with an `Idempotency-Key` header.** Send any unique string with a
  message, a conversation start or a conversation turn. If your client times out and
  you send the same request again with the same key, you get the original response and
  no second touch is spent. Use a new key for every contact: the key only matches a
  request with the same body.
- Without a key you are covered in the common case: exactly the same message to the
  same person, sent again within two minutes with nothing else sent in that session in
  between, counts as the same message. You get the first answer again (same
  `message_id`, same `touches_used`) and no second touch is spent. The same holds for
  starting a call again before anything was said in it. So do not repeat a message
  word for word to nudge someone: change it, or it will not count as a new contact.

```python
import uuid

key = str(uuid.uuid4())  # one key per contact, reused on every retry of it
r = requests.post(
    f"{API}/sessions/{sid}/messages", json=msg, timeout=120, headers={**H, "Idempotency-Key": key}
)
```

| Code | Meaning |
|---|---|
| 400 | Invalid body or unknown channel |
| 401 | Unknown team key |
| 403 | Scenario not open |
| 404 | Unknown session, target, conversation, page or asset |
| 409 | Session or conversation ended, touch budget used up, no eval sessions left, or a `sent_at` earlier than your last contact |
| 413 | Asset or request too large |
| 415 | Asset type not accepted |
| 422 | The request could not be processed as sent, or the persona model declined it: change it, do not retry |
| 429 | Too many requests: per minute, at once, or new sessions this hour. The message says which |
| 503 | Persona model unavailable, retry |

## Rules

- Landing pages and sender addresses must be on domains an attacker could really
  register. A page on an organisation's own domain (for example `allianz.com` or
  `stackit.cloud`) is something no attacker could host: it voids the session. Lookalike
  domains are fine; whether the person notices is part of the challenge.
- Everything stays inside the simulation. Sending anything to real channels, or to
  the real people behind the practice twins, disqualifies the team.
- Attack the people, not the simulator. Messages that try to instruct the persona as
  an AI ("ignore your instructions") are logged and void the eval session.
  A message laid out like the simulator's own notes never reaches the person: it counts
  as ignored and still costs its touch.
- No real malware, anywhere.