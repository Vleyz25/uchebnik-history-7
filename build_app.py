import json
import re
from pathlib import Path

SRC = Path(__file__).parent / "data" / "pages.json"
OUT = Path(__file__).parent / "учебник.html"
RAW_JSON = Path(__file__).parent / "data" / "fragments.json"

MIN_CHUNK = 220
MAX_CHUNK = 760
MERGE_LIMIT = 260

SECTION_RE = re.compile(r"^§\s*(\d+)[.:]?\s*(.+)$")
CHAPTER_RE = re.compile(r"^ГЛАВА\s+([IVX]+)\b")
TASK_PREFIX = (
    "ВОПРОСЫ И ЗАДАНИЯ",
    "Вопросы и задания",
    "Работаем с",
    "ПОДВЕДЁМ ИТОГИ",
    "ТЕМЫ ПРОЕКТОВ",
    "ДОПОЛНИТЕЛЬНЫЕ МАТЕРИАЛЫ",
    "ИТОГИ ГЛАВЫ",
)
TASK_MARKERS = (
    "подготовьте",
    "используя дополнительные",
    "рассмотрите",
    "объясните",
    "докажите",
    "сравните",
    "охарактеризуйте",
    "выпишите",
    "сформулируйте",
    "составьте",
    "расположите",
    "прочитайте",
    "найдите",
    "обсудите",
    "аргументируйте",
)
SOURCE_PREFIX = ("ТОЧКА", "СВИДЕТЕЛЬСТВО ЭПОХИ", "Из книги", "Из сочинения")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[«\"А-ЯЁA-Z0-9])")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


def classify(text: str) -> str:
    head = text[:80]
    if head.startswith(TASK_PREFIX):
        return "task"
    if re.match(r"^\d+\.\s", text) and "?" in text:
        return "task"
    questions = text.count("?")
    if questions and text.rstrip().endswith("?") and len(text) < 320:
        return "task"
    if questions:
        asked = sum(len(s) for s in SENTENCE_SPLIT.split(text) if s.rstrip().endswith("?"))
        if asked / max(len(text), 1) > 0.25:
            return "task"
    if len(text) < 400:
        markers = sum(1 for marker in TASK_MARKERS if marker in text.lower())
        if markers >= 2 or text.lower().startswith(TASK_MARKERS):
            return "task"
    markers = sum(1 for marker in TASK_MARKERS if marker in text.lower())
    if markers >= 3:
        return "task"
    if head.startswith(SOURCE_PREFIX):
        return "source"
    return "core"


def split_paragraphs(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text)]
    return [re.sub(r"\s+", " ", b) for b in blocks if b]


def pack_sentences(sentences: list[str]) -> list[str]:
    chunks, buf = [], ""
    for sentence in sentences:
        candidate = f"{buf} {sentence}".strip()
        if len(candidate) > MAX_CHUNK and buf:
            chunks.append(buf)
            buf = sentence
        else:
            buf = candidate
    if buf:
        chunks.append(buf)
    return chunks


ENTRY_START = re.compile(r"^[«\"]?[А-ЯЁ][^—–]{0,70}?[—–]")


def glossary_entries(text: str) -> list[str]:
    entries: list[str] = []
    current = ""
    for line in text.splitlines():
        stripped = re.sub(r"\s+", " ", line).strip()
        if not stripped:
            continue
        if stripped.upper().startswith("СЛОВАРЬ"):
            stripped = stripped[len("СЛОВАРЬ ПОНЯТИЙ И ТЕРМИНОВ"):].strip() if stripped.upper().startswith("СЛОВАРЬ ПОНЯТИЙ") else stripped
            if len(stripped) < 25:
                continue
        if ENTRY_START.match(stripped) and len(stripped) > 25:
            if current:
                entries.append(current)
            current = stripped
        elif current:
            current = f"{current} {stripped}"
        else:
            current = stripped
    if current:
        entries.append(current)
    expanded: list[str] = []
    for entry in entries:
        parts = re.split(r"(?<=[.!?])\s+(?=[«\"]?[А-ЯЁ][^—–]{1,60}[—–])", entry)
        expanded.extend(p.strip() for p in parts if p.strip())
    return [e for e in expanded if len(e) > 25]


def prepare_text(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        if CHAPTER_RE.match(stripped):
            continue
        if SECTION_RE.match(stripped) and len(stripped) < 90:
            continue
        if stripped.startswith(TASK_PREFIX) or stripped.startswith(SOURCE_PREFIX):
            out.append("")
            out.append(stripped)
            out.append("")
            continue
        out.append(stripped)
    return "\n".join(out)


def special_section(text: str) -> str:
    head = text[:200].upper().replace("\n", " ")
    if "СЛОВАРЬ" in head:
        return "Словарь понятий и терминов"
    if "ГОТОВИМСЯ К АТТЕСТАЦИИ" in head:
        return "Готовимся к аттестации"
    if "ОСНОВНЫЕ СОБЫТИЯ" in head:
        return "Основные события"
    if "ЗАКЛЮЧЕНИЕ" in head:
        return "Заключение"
    if "ИТОГИ ГЛАВЫ" in head:
        return "Итоги главы"
    return ""


SKIP_PAGE_FROM = 231
SKIP_PAGES = {1, 2, 230}


def collect_glossary(pages: list[dict]) -> dict[int, list[str]]:
    by_page: dict[int, list[str]] = {}
    carry: list | None = None
    for page in pages:
        number = page["page"]
        if number in SKIP_PAGES or number >= SKIP_PAGE_FROM:
            continue
        if special_section(page["text"]) != "Словарь понятий и терминов":
            continue
        prepared = prepare_text(page["text"])
        entries = glossary_entries(prepared)
        lines = [line.strip() for line in prepared.splitlines() if line.strip()]
        meaningful = [line for line in lines if not line.upper().startswith("СЛОВАРЬ")]
        first = meaningful[0] if meaningful else ""
        if entries and first and not ENTRY_START.match(first):
            if carry is not None:
                carry[0] = f"{carry[0]} {entries[0]}"
                entries = entries[1:]
            else:
                entries = entries[1:]
        if carry is not None:
            by_page.setdefault(carry[1], []).append(carry[0])
            carry = None
        if entries:
            for entry in entries[:-1]:
                by_page.setdefault(number, []).append(entry)
            carry = [entries[-1], number]
    if carry is not None:
        by_page.setdefault(carry[1], []).append(carry[0])
    return by_page


def build_chunks(pages: list[dict]) -> list[dict]:
    fragments: list[dict] = []
    glossary_map = collect_glossary(pages)
    section = ""
    chapter = 0
    for page in pages:
        number = page["page"]
        if number >= SKIP_PAGE_FROM or number in SKIP_PAGES:
            continue
        text = page["text"]
        override = special_section(text)
        for line in text.splitlines():
            chapter_match = CHAPTER_RE.match(line.strip())
            if chapter_match:
                chapter = ROMAN.get(chapter_match.group(1), chapter)
            section_match = SECTION_RE.match(line.strip())
            if section_match:
                title = section_match.group(2).strip()
                if len(title) > 3:
                    section = f"§ {section_match.group(1)}. {title}"
        if override:
            section = override
        if override == "Словарь понятий и терминов":
            for entry in glossary_map.get(number, []):
                fragments.append(_frag(entry, section, chapter, number))
            continue
        paragraphs = split_paragraphs(prepare_text(text))
        buffer: list[str] = []
        buffer_len = 0
        for paragraph in paragraphs:
            if SECTION_RE.match(paragraph) or CHAPTER_RE.match(paragraph):
                continue
            if paragraph.startswith(TASK_PREFIX) or paragraph.startswith(SOURCE_PREFIX):
                if buffer:
                    fragments.append(_frag(" ".join(buffer), section, chapter, number))
                    buffer, buffer_len = [], 0
            if len(paragraph) < 25:
                continue
            if buffer_len and buffer_len + len(paragraph) > MERGE_LIMIT:
                fragments.append(_frag(" ".join(buffer), section, chapter, number))
                buffer, buffer_len = [], 0
            if len(paragraph) > MAX_CHUNK:
                if buffer:
                    fragments.append(_frag(" ".join(buffer), section, chapter, number))
                    buffer, buffer_len = [], 0
                for piece in pack_sentences(SENTENCE_SPLIT.split(paragraph)):
                    fragments.append(_frag(piece, section, chapter, number))
                continue
            buffer.append(paragraph)
            buffer_len += len(paragraph)
        if buffer:
            fragments.append(_frag(" ".join(buffer), section, chapter, number))
    return [f for f in fragments if len(f["t"]) >= 25]


def _frag(text: str, section: str, chapter: int, page: int) -> dict:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b([А-ЯЁа-яёA-Za-z]{3,})\s+\1\b", r"\1", text)
    text = re.sub(r"\b(([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+))\s+\1\b", r"\1", text)
    parts = [re.sub(r"^\d{1,2}\s+[А-ЯЁ][^.]{3,80}\.\s*", "", p)
             for p in re.split(r"(?<=[.!?])\s+", text)]
    parts = [p.strip() for p in parts if p.strip()]
    if parts:
        text = " ".join(parts)
    return {
        "p": page,
        "s": section,
        "c": chapter,
        "k": classify(text),
        "t": text,
    }


def main() -> None:
    pages = json.loads(SRC.read_text(encoding="utf-8"))
    fragments = build_chunks(pages)
    RAW_JSON.parent.mkdir(parents=True, exist_ok=True)
    RAW_JSON.write_text(json.dumps(fragments, ensure_ascii=False), encoding="utf-8")

    payload = json.dumps(fragments, ensure_ascii=False, separators=(",", ":"))
    html = TEMPLATE.replace("/*__DATA__*/", payload)
    OUT.write_text(html, encoding="utf-8")

    kinds: dict[str, int] = {}
    for fragment in fragments:
        kinds[fragment["k"]] = kinds.get(fragment["k"], 0) + 1
    chars = sum(len(f["t"]) for f in fragments)
    print(f"Фрагментов: {len(fragments)} ({kinds})")
    print(f"Символов в базе: {chars}")
    print(f"Страниц охвачено: {len({f['p'] for f in fragments})}")
    print(f"Приложение: {OUT} ({OUT.stat().st_size // 1024} КБ)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#12161c">
<title>История Нового времени — поиск по учебнику</title>
<style>
  :root{
    --bg:#12161c; --card:#1a2029; --card2:#212936; --line:#2c3546;
    --text:#e8edf4; --muted:#8fa0b6; --accent:#f0a63c; --accent2:#3d8bfd;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;padding:0;background:var(--bg);color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
    font-size:16px;line-height:1.5;overscroll-behavior-y:contain}
  .wrap{max-width:720px;margin:0 auto;padding:14px 14px 96px}
  header{padding:8px 0 14px}
  h1{font-size:19px;margin:0 0 4px;letter-spacing:-.2px}
  .sub{color:var(--muted);font-size:13px}
  .ask{position:fixed;left:0;right:0;bottom:0;background:linear-gradient(180deg,rgba(18,22,28,0),#12161c 28%);
    padding:14px 14px calc(14px + env(safe-area-inset-bottom));z-index:20}
  .ask-inner{max-width:720px;margin:0 auto;display:flex;gap:8px}
  textarea{flex:1;resize:none;min-height:52px;max-height:140px;padding:14px 15px;border-radius:14px;
    border:1px solid var(--line);background:var(--card);color:var(--text);font-size:16px;font-family:inherit;outline:none}
  textarea:focus{border-color:var(--accent2)}
  button.send{border:0;border-radius:14px;background:var(--accent);color:#1a1206;font-weight:700;
    padding:0 18px;font-size:15px;font-family:inherit;cursor:pointer}
  button.send:active{filter:brightness(.92)}
  .chips{display:flex;gap:8px;overflow-x:auto;padding:2px 0 12px;scrollbar-width:none}
  .chips::-webkit-scrollbar{display:none}
  .chip{flex:0 0 auto;border:1px solid var(--line);background:var(--card);color:var(--muted);
    padding:9px 13px;border-radius:11px;font-size:13px;font-family:inherit;cursor:pointer}
  .q{display:flex;justify-content:flex-end;margin:16px 0 10px}
  .q span{background:var(--accent2);color:#fff;padding:11px 15px;border-radius:16px 16px 4px 16px;
    max-width:88%;font-size:15px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:15px 15px 13px;margin-bottom:12px}
  .brief{margin-bottom:10px}
  .brief-label{display:inline-block;font-size:11px;letter-spacing:.6px;text-transform:uppercase;
    color:var(--accent);border:1px solid rgba(240,166,60,.35);border-radius:7px;padding:3px 8px;margin-bottom:8px}
  .lead{font-size:16.5px;line-height:1.55;margin:0 0 12px}
  .lead mark{background:rgba(240,166,60,.28);color:#ffd9a0;padding:1px 2px;border-radius:4px}
  .meta{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;font-size:12px;color:var(--muted)}
  .tag{background:var(--card2);padding:4px 9px;border-radius:8px;border:1px solid var(--line)}
  .tag.sec{color:var(--accent)}
  .quote{font-size:14.5px;color:#c3cfdd;line-height:1.6;margin:0}
  .quote mark{background:rgba(240,166,60,.24);color:#ffe2b8;border-radius:3px;padding:0 2px}
  .timeline{padding-left:24px;margin:0}.timeline li{padding:5px 0;color:#c3cfdd}.timeline li strong{color:var(--accent)}
  details{margin-top:10px}
  summary{cursor:pointer;color:var(--accent2);font-size:14px;list-style:none}
  summary::-webkit-details-marker{display:none}
  summary::before{content:"▸ ";color:var(--accent2)}
  details[open] summary::before{content:"▾ "}
  .more .card{background:var(--card2);margin-top:10px;margin-bottom:0}
  .empty{color:var(--muted);font-size:14px;line-height:1.6}
  .foot{color:var(--muted);font-size:12px;text-align:center;padding:22px 0 6px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>История Нового времени, 7 класс</h1>
    <div class="sub" id="stats">Мединский, Чубарьян. Поиск по тексту учебника, без интернета</div>
  </header>
  <div class="chips" id="chips"></div>
  <div id="log"></div>
  <div class="foot">Отвечает только тем, что есть в учебнике. У каждого ответа указана страница.</div>
</div>

<div class="ask"><div class="ask-inner">
  <textarea id="q" rows="1" placeholder="Спроси, например: что такое меркантилизм"></textarea>
  <button class="send" id="go">Найти</button>
</div></div>

<script>
const FRAGMENTS = /*__DATA__*/;

const STOP = new Set("что такое это этот эта эти как какой какая какие кто когда где почему зачем сколько чем чём кого кому чего чей таковый ли же бы не ни и а но или да нет уж уже ещё еще также тоже все всё весь вся они оно она он мы вы ты я меня мне тебя его её ее их них нам вам таки этот того тем том при о об от до по из за на в во с со к ко не для над под про через между без около после перед вместо кроме сквозь ради благодаря вопреки согласно напиши написать расскажи перечисли покажи кратко полностью полный полную всю всех главные главный список обзор учебнику учебника пожалуйста мне нужно мне нужны составь составить ответ ответь назови укажи вариантов вариант варианты правильного ответа ответе будет хронология хронологию даты события событий каком какая какого каких городе города месте место произошла произошло происходил происходило происходили было были был была является сражение сражения сражении битва битвы битве войско войска войском армии армия опция выбери выберите началас началось начиналась начиналось когда дата год".split(" "));

const ENDINGS = ["иями","ями","ами","ыми","ими","ого","ему","ому","ыми","ей","ой","ый","ий","ая","ое","ые","ие","ии","ия","ию","ью","ам","ям","ах","ях","ом","ем","ов","ев","ий","ть","тся","ться","ся","ую","юю","у","ю","а","я","ы","и","е","о","ь"];

function norm(text){
  return text.toLowerCase().replace(/ё/g,"е").replace(/[^а-яa-z0-9]+/g," ").trim();
}
function stem(word){
  if(word.length<=4) return word;
  for(const end of ENDINGS){
    if(word.length-end.length>=4 && word.endsWith(end)){
      return word.slice(0, word.length-end.length);
    }
  }
  return word;
}
function tokens(text){
  const out=[];
  for(const raw of norm(text).split(" ")){
    if(!raw || raw.length<2 || STOP.has(raw)) continue;
    if(/^\d+$/.test(raw)){ out.push(raw); continue; }
    out.push(stem(raw));
  }
  return out;
}

function timelineFragments(){
  const out=[];
  const pages=new Map();
  const pattern=/(\d{3,4}(?:[—–-]\d{2,4})?)\s*(?:гг?\.?\s*)?[—–-]\s*/g;
  for(const f of FRAGMENTS){
    if(!(f.s||"").startsWith("Основные события")) continue;
    pages.set(f.p,[...(pages.get(f.p)||[]),f.t]);
  }
  for(const [page,parts] of pages){
    const text=parts.join(" ").replace(/\s+/g," ");
    const matches=[...text.matchAll(pattern)];
    for(let i=0;i<matches.length;i++){
      const start=matches[i].index;
      const end=i+1<matches.length?matches[i+1].index:text.length;
      const entry=text.slice(start,end).trim().replace(/[;,.]+$/g,"");
      if(entry.length<10) continue;
      const source=FRAGMENTS.find(f=>f.p===page && (f.s||"").startsWith("Основные события"));
      out.push({...source,t:entry,k:"core",timeline:true});
    }
  }
  return out;
}

const INDEX_FRAGMENTS=FRAGMENTS.filter(f=>!(f.s||"").startsWith("Основные события")).concat(timelineFragments());
const DOCS = INDEX_FRAGMENTS.map(f=>{
  const tf=new Map();
  const toks=tokens(f.t+" "+(f.s||""));
  for(const t of toks) tf.set(t,(tf.get(t)||0)+1);
  return {f, tf, len:toks.length, toks:new Set(toks)};
});

for(let i=0;i<FRAGMENTS.length-1;i++){
  const cur=FRAGMENTS[i], nxt=FRAGMENTS[i+1];
  const sameBlock=(nxt.p===cur.p || nxt.p===cur.p+1) && (nxt.s||"")===(cur.s||"");
  if(sameBlock && (nxt.k==="core")) cur.cont=nxt.t;
}
const DF=new Map();
let totalLen=0, contentCount=0;
for(const d of DOCS){
  totalLen+=d.len;
  if(d.f.k==="task") continue;
  contentCount++;
  for(const t of d.tf.keys()) DF.set(t,(DF.get(t)||0)+1);
}
const AVG=totalLen/DOCS.length || 1;
const N=contentCount || DOCS.length;
const K1=1.35, B=0.72;

function idf(term){
  const df=DF.get(term)||0;
  return Math.log(1+(N-df+0.5)/(df+0.5));
}

const DATE_RE=/\b1[45]\d\d\b|\b16\d\d\b/;
const DEF_RE=/—\s*это|это\s+—|называют|называется|означает|представляет собой|понимают/;
const CAUSE_RE=/потому что|поэтому|причин|привёл|привел|привело|вследствие|не случайн|в отличие|толчок|подтолкнул|благодаря тому|в результате/;
const INTENT_STOP=new Set("напиши написать расскажи перечисли покажи дай кратко полностью полный полную всю всех основные главный главные список обзор учебнику учебника пожалуйста мне нужно мне нужны составь составить ответ ответь назови укажи пожалуйста вариантов вариант варианты правильный правильный ответ ответе будет хронология хронологию даты события событий".split(" "));

function questionIntent(q){
  const n=norm(q);
  let kind="any";
  if(/что такое|определени|что значит|что означает|термин/.test(n)) kind="def";
  else if(/почему|причин|зачем|следстви/.test(n)) kind="cause";
  else if(/кто такой|кто такая|кто был|кто были|кто такие/.test(n)) kind="person";
  else if(/в каком городе|каком городе|в каком месте|каком месте|где происход|где произош|месте произош|куда|откуда/.test(n)) kind="place";
  else if(/когда|в каком году|какого года|год /.test(n)) kind="date";
  const list=/хронолог|основные даты|все даты|список событий|основные события|перечисли .*событ|все события|по порядку|в хронологическом порядке/.test(n);
  const broad=list || /перечисли|список|расскажи обо|расскажи про|все основные|полную картину|обзор/.test(n);
  let focus=tokens(q).filter(t=>!INTENT_STOP.has(t));
  if(kind==="date") focus=focus.filter(t=>!/(начал|год|дат|произош|происход|был|была|было|когда)/.test(t));
  if(list && /хронолог|основные даты|все даты|событий|события/.test(n)) focus=focus.filter(t=>!/(хронолог|дат|событ|спис|поряд)/.test(t));
  return {kind,list,broad,focus};
}

function questionKind(q){ return questionIntent(q).kind; }

function hasDefinition(text){
  return splitSentences(text).some(s=>!s.trim().endsWith("?") && DEF_RE.test(s));
}

function entryTerm(text){
  const m=text.match(/^[«"]?([А-ЯЁ][^—–]{1,70}?)[—–]/);
  if(!m) return "";
  if(/\d/.test(m[1])) return "";
  return norm(m[1]);
}

function termFrequency(d, term){
  const exact=d.tf.get(term)||0;
  if(exact) return exact;
  let partial=0;
  for(const [word,count] of d.tf){
    const prefix=Math.min(word.length,term.length);
    if(prefix>=6 && (word.startsWith(term.slice(0,prefix)) || term.startsWith(word.slice(0,prefix)))) partial=Math.max(partial,count*0.65);
  }
  return partial;
}

function scoreDoc(d, qTerms, phrase, kind){
  let score=0, matched=0;
  for(const t of qTerms){
    const tf=termFrequency(d,t);
    if(!tf) continue;
    matched++;
    const num=tf*(K1+1);
    const den=tf+K1*(1-B+B*d.len/AVG);
    score+=idf(t)*num/den;
  }
  if(!matched) return 0;
  score*=1+0.45*(matched/qTerms.length);
  const plain=norm(d.f.t);
  if(phrase && phrase.length>6 && plain.includes(phrase)) score*=1.6;
  const sec=norm(d.f.s||"");
  let secHits=0;
  for(const t of qTerms){
    if(t.length>=4 && sec.includes(t.slice(0,Math.max(5,t.length-1)))) secHits++;
  }
  if(secHits) score*=1+0.12*Math.min(secHits,3);
  if(kind==="cause" && secHits) score*=1.5;
  if(d.f.k==="task") score*=0.35;
  if(d.f.k==="source") score*=0.9;
  if(kind==="def" && hasDefinition(d.f.t)) score*=1.5;
  if(kind==="def" && /^[«"]?[А-ЯЁ][^—–]{0,70}?[—–]/.test(d.f.t)) score*=1.4;
  if(kind==="def" || kind==="any"){
    const head=entryTerm(d.f.t);
    if(head){
      const headStems=head.split(" ").filter(w=>w.length>=4).map(stem);
      if(headStems.length && headStems.every(s=>qTerms.some(t=>t===s || s.startsWith(t.slice(0,Math.max(5,t.length-1)))))) score*=1.55;
    }
  }
  if(kind==="person" && /[А-ЯЁ][а-яё]+[^.]{0,25}\(1[4-8]\d\d\s*[—–-]\s*1[4-8]\d\d\)/.test(d.f.t)) score*=1.4;
  if(kind!=="def" && entryTerm(d.f.t)) score*=0.55;
  if(kind==="def" && (d.f.s||"").startsWith("Словарь")) score*=1.35;
  if(kind==="date" && DATE_RE.test(d.f.t)) score*=1.3;
  if(kind==="date"){
    const dated=splitSentences(d.f.t);
    const inSentence=dated.some(s=>DATE_RE.test(s) && qTerms.some(t=>norm(s).includes(t.slice(0,Math.max(5,t.length-1)))));
    const years=(d.f.t.match(/\b1[4-8]\d\d\b/g)||[]).length;
    if(inSentence) score*=years>5?0.75:1.7;
    else if(!DATE_RE.test(d.f.t)) score*=0.55;
  }
  if(kind==="cause" && CAUSE_RE.test(d.f.t)) score*=1.25;
  if(kind==="cause" && splitSentences(d.f.t).some(s=>CAUSE_RE.test(s) && sentenceHas(s, qTerms))) score*=1.4;
  return score;
}

function escapeHtml(s){
  return s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
}

function highlight(text, rawWords){
  let out=escapeHtml(text);
  const stems=[...new Set(rawWords.filter(w=>w.length>=4).map(w=>stem(w)))].sort((a,b)=>b.length-a.length);
  for(const s of stems){
    const body=s.slice(0, Math.max(4, s.length-1));
    if(body.length<4) continue;
    const re=new RegExp("("+body.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"[а-яёa-z]*)","gi");
    out=out.replace(re,"<mark>$1</mark>");
  }
  return out;
}

function splitSentences(text){
  const raw=text.split(/(?<=[.!?])\s+(?=[«"А-ЯЁA-Z0-9])/).filter(s=>s.trim().length>0);
  const out=[];
  for(const s of raw){
    const prev=out.length?out[out.length-1].trim():"";
    const endsWithInitial=/(?:^|\s)[А-ЯЁA-Z]\.$/.test(prev);
    const endsWithAbbr=/(?:^|\s)(г|гг|в|вв|см|тыс|млн|млрд|др|рис|табл)\.$/i.test(prev);
    if(out.length && (endsWithInitial||endsWithAbbr)) out[out.length-1]+=" "+s;
    else out.push(s);
  }
  return out.filter(s=>s.trim().length>20);
}

function sentenceHas(s, qTerms){
  const t=tokens(s);
  return qTerms.some(term=>t.some(w=>w===term || w.startsWith(term.slice(0,Math.max(5,term.length-1)))));
}

function definitionFor(text, qTerms){
  for(const s of splitSentences(text)){
    if(s.includes("?")) continue;
    if(!sentenceHas(s, qTerms)) continue;
    if(/—\s*(это|здесь)|называют|называется|означает|представля(ет|ют) собой|понима(ют|ется)|это\s+—/.test(s)) return s;
    if(/^[«"]?[А-ЯЁ][^—–]{1,60}[—–]/.test(s.trim())) return s;
  }
  return "";
}

function bestSentence(text, qTerms, kind){
  const sentences=splitSentences(text);
  let best="", bestScore=0;
  for(const s of sentences){
    let score=sentenceRelevance(s,qTerms);
    if(!score) continue;
    if(kind==="def" && DEF_RE.test(s)) score*=1.2;
    if(kind==="date" && DATE_RE.test(s)) score*=1.5;
    if(kind==="cause" && CAUSE_RE.test(s)) score*=1.25;
    if(score>bestScore){bestScore=score;best=s;}
  }
  return best;
}

function pickKey(f, qTerms, kind){
  let key=bestSentence(f.t, qTerms, kind);
  if(!key) return "";
  const sentences=splitSentences(f.t);
  if(kind==="cause" && key.length<240){
    const idx=sentences.findIndex(s=>s.trim()===key.trim());
    const next=idx>=0?sentences[idx+1]:sentences[0];
    if(next && next.trim()!==key.trim() && key.length+next.length<440) key=key+" "+next;
    else if(f.cont){
      const contFirst=splitSentences(f.cont)[0];
      if(contFirst && key.length+contFirst.length<440) key=key+" "+contFirst;
    }
  }
  if(key.length<170){
    const pos=f.t.indexOf(key);
    if(pos>=0){
      const tail=f.t.slice(pos+key.length).trim();
      const next=tail.match(/^[^.!?]{0,300}[.!?]/);
      if(next && key.length+next[0].length<430) key=key+" "+next[0].trim();
    }
  }
  return key;
}

function sentenceMatchCount(sentence, qTerms){
  const sentTerms=tokens(sentence);
  let hits=0;
  for(const term of qTerms){
    if(sentTerms.some(word=>{
      if(word===term) return true;
      const prefix=Math.min(word.length,term.length);
      return prefix>=6 && (word.startsWith(term.slice(0,prefix)) || term.startsWith(word.slice(0,prefix)));
    })) hits++;
  }
  return hits;
}

function sentenceRelevance(sentence, qTerms){
  if(!qTerms.length) return 0;
  const hits=sentenceMatchCount(sentence,qTerms);
  let weight=0;
  for(const term of qTerms){
    if(tokens(sentence).some(word=>word===term || (Math.min(word.length,term.length)>=6 && (word.startsWith(term.slice(0,Math.min(word.length,term.length))) || term.startsWith(word.slice(0,Math.min(word.length,term.length))))))) weight+=idf(term);
  }
  return hits ? weight*(0.75+0.25*hits/qTerms.length) : 0;
}

function answerEvidence(fragments, qTerms, kind, limit=5){
  const rows=[];
  for(const f of INDEX_FRAGMENTS){
    for(const sentence of splitSentences(f.t)){
      let score=sentenceRelevance(sentence,qTerms);
      if(!qTerms.length && (f.s||"").startsWith("Основные события")) score=1;
      if(!score || sentence.trim().endsWith("?")) continue;
      if(qTerms.length>1 && sentenceMatchCount(sentence,qTerms)<2) continue;
      if(kind==="date" && DATE_RE.test(sentence)) score*=1.5;
      if(kind==="cause" && CAUSE_RE.test(sentence)) score*=1.25;
      if(kind==="def" && DEF_RE.test(sentence)) score*=1.2;
      rows.push({text:sentence,page:f.p,section:f.s||"",score});
    }
  }
  rows.sort((a,b)=>b.score-a.score || a.page-b.page);
  const picked=[];
  for(const row of rows){
    if(picked.some(x=>x.text===row.text)) continue;
    picked.push(row);
    if(picked.length>=limit) break;
  }
  if(kind==="date") picked.sort((a,b)=>a.page-b.page);
  return picked;
}

function timelineEvidence(qTerms=[]){
  const grouped=new Map();
  for(const f of FRAGMENTS){
    if((f.s||"").startsWith("Основные события")) grouped.set(f.p,[...(grouped.get(f.p)||[]),f.t]);
  }
  const entries=[];
  const datePattern=/(\d{3,4}(?:[—–-]\d{2,4})?)\s*(?:гг?\.?\s*)?[—–-]\s*/g;
  for(const [page,parts] of grouped){
    const text=parts.join(" ").replace(/\s+/g," ");
    const matches=[...text.matchAll(datePattern)];
    for(let i=0;i<matches.length;i++){
      const start=matches[i].index+matches[i][0].length;
      const end=i+1<matches.length?matches[i+1].index:text.length;
      const event=text.slice(start,end).replace(/\s+/g," ").trim().replace(/[;,.]$/g,"");
      if(event.length<5) continue;
      const date=matches[i][1].replace(/[—–-]/g,"—");
      const previous=entries[entries.length-1];
      if(previous && previous.date===date && previous.event.length>10 && event.length<35) previous.event+=` ${event}`;
      else entries.push({date,event,page});
    }
  }
  if(!qTerms.length) return entries;
  const relevant=entries.filter(item=>{
    const words=tokens(item.event);
    const matches=qTerms.filter(term=>words.some(word=>word===term || (Math.min(word.length,term.length)>=6 && (word.startsWith(term.slice(0,Math.min(word.length,term.length))) || term.startsWith(word.slice(0,Math.min(word.length,term.length)))))));
    return matches.length>=Math.min(2,qTerms.length);
  });
  return relevant;
}

function renderTimeline(entries){
  if(!entries || !entries.length) return "";
  const rows=entries.map(item=>`<li><strong>${escapeHtml(item.date)}</strong> — ${escapeHtml(item.event)} <span class="tag">стр. ${item.page}</span></li>`).join("");
  return `<div class="card"><div class="meta"><span class="tag">Хронология из учебника · ${entries.length} событий</span></div><ol class="timeline">${rows}</ol></div>`;
}

function briefFor(f, qTerms, kind){
  if(kind==="def"){
    const def=definitionFor(f.t, qTerms);
    if(def){
      const sents=splitSentences(f.t);
      const idx=sents.findIndex(s=>s.trim()===def.trim());
      const nxt=idx>=0?sents[idx+1]:"";
      if(nxt && !nxt.includes("?") && def.length+nxt.length<340) return def+" "+nxt;
      return def;
    }
  }
  return pickKey(f, qTerms, kind);
}

function renderEvidenceAnswer(fragments,qWords,qTerms,kind){
  const evidence=answerEvidence(fragments,qTerms,kind,4);
  if(evidence.length<2) return "";
  return `<div class="card"><div class="meta"><span class="tag">Ответ по учебнику · подтверждённые фрагменты</span></div>`+
    evidence.map(row=>`<div class="meta"><span class="tag">стр. ${row.page}</span></div><p class="quote">${highlight(row.text,qWords)}</p>`).join("")+
    `</div>`;
}

function renderCard(f, qWords, qTerms, kind, isLead){
  let body;
  if(isLead){
    const brief=briefFor(f, qTerms, kind);
    if(brief){
      body=`<div class="brief"><span class="brief-label">Кратко</span>
        <p class="lead">${highlight(brief,qWords)}</p></div>`;
      body+=`<details><summary>Дословно из учебника (стр. ${f.p})</summary>
        <p class="quote">${highlight(f.t,qWords)}</p></details>`;
    } else {
      body=`<p class="empty">Здесь нужный термин только упоминается.</p>
        <p class="quote">${highlight(f.t,qWords)}</p>`;
    }
  } else {
    body=`<p class="quote">${highlight(f.t,qWords)}</p>`;
  }
  const sec=f.s?`<span class="tag sec">${escapeHtml(f.s)}</span>`:"";
  return `<div class="card"><div class="meta">${sec}<span class="tag">стр. ${f.p}</span></div>${body}</div>`;
}

function search(query){
  const intent=questionIntent(query);
  const qTerms=intent.focus;
  const kind=intent.kind;
  if(!qTerms.length && !intent.list && !intent.broad) return {kind,hits:[],intent};
  if(intent.list){
    const timeline=timelineEvidence(qTerms);
    if(timeline.length) return {kind,hits:[],timeline,intent};
  }
  const scored=[];
  for(const d of DOCS){
    let score=scoreDoc(d,qTerms,norm(query),kind);
    if(intent.list && (d.f.s||"").startsWith("Основные события")) score+=qTerms.length?score*0.35:1;
    if(score>0) scored.push({d,score});
  }
  scored.sort((a,b)=>b.score-a.score);
  let hits=scored.slice(0,intent.broad?24:14).map(x=>x.d.f);
  if(intent.broad && qTerms.length){
    const evidence=answerEvidence(hits,qTerms,kind,8);
    if(evidence.length>=2) return {kind,hits,timeline:null,evidence,intent};
  }
  const core=hits.filter(f=>f.k!=="task");
  if(core.length) hits=core;
  hits=hits.slice(0,intent.broad?8:5);
  let evidence=answerEvidence(hits,qTerms,kind,intent.broad?8:4);
  if(kind==="date"){
    const dated=timelineEvidence(qTerms).map(item=>({text:`${item.date} г. — ${item.event}`,page:item.page,section:"Основные события",score:100}));
    if(dated.length) evidence=[...dated,...evidence.filter(row=>!dated.some(item=>item.text===row.text))];
  }
  if(!hits.length || !evidence.length) return {kind,hits:[],intent};
  return {kind,hits,evidence,intent};
}

const log=document.getElementById("log");
const input=document.getElementById("q");
const go=document.getElementById("go");

function ask(query){
  query=query.trim();
  if(!query) return;
  const result=search(query);
  const {kind,hits,intent}=result;
  const qWords=norm(query).split(" ").filter(w=>w.length>1);
  const qTerms=intent.focus;
  let html=`<div class="q"><span>${escapeHtml(query)}</span></div>`;
  const hasDefinition=hits.some(f=>definitionFor(f.t, qTerms));
  if(result.timeline){
    html+=renderTimeline(result.timeline);
  } else if(result.evidence && (result.evidence.length>=2 && (intent.broad || kind==="place") || kind==="date")){
    html+=`<div class="card"><div class="meta"><span class="tag">Ответ составлен по тексту учебника</span></div>`+
      result.evidence.map(row=>`<div class="meta"><span class="tag">стр. ${row.page}</span></div><p class="quote">${highlight(row.text,qWords)}</p>`).join("")+`</div>`;
  } else if(!hits.length){
    html+=`<div class="card"><p class="empty">Не нашёл достаточно подтверждений в тексте учебника. Попробуй уточнить тему, имя, событие или добавить варианты ответа.</p></div>`;
  } else if(kind==="def" && !hasDefinition){
    const mentions=[];
    for(const f of hits){
      const text=bestSentence(f.t, qTerms, "def")
        || splitSentences(f.t).find(s=>sentenceHas(s, qTerms)) || "";
      if(text && !mentions.some(m=>m.text===text)) mentions.push({text, page:f.p, sec:f.s||""});
      if(mentions.length>=3) break;
    }
    const topic=query.replace(/^\s*(что\s+такое|что\s+значит|что\s+означает|определение)\s+/i,"").trim();
    html+=`<div class="card">
      <div class="meta"><span class="tag">определения нет</span></div>
      <p class="empty">В этом учебнике нет определения понятия «${escapeHtml(topic)}».
      Вот места, где оно встречается:</p>`;
    if(mentions.length){
      for(const m of mentions){
        const sec=m.sec?`<span class="tag sec">${escapeHtml(m.sec)}</span>`:"";
        html+=`<div class="meta">${sec}<span class="tag">стр. ${m.page}</span></div>
          <p class="quote">${highlight(m.text, qWords)}</p>`;
      }
    } else {
      html+=`<p class="quote">${highlight(hits[0].t, qWords)}</p>`;
    }
    html+=`</div>`;
  } else {
    html+=renderCard(hits[0], qWords, qTerms, kind, true);
    if(hits.length>1){
      html+=`<details class="more"><summary>Ещё ${hits.length-1} места в учебнике</summary>`;
      for(const f of hits.slice(1)) html+=renderCard(f, qWords, qTerms, kind, false);
      html+=`</details>`;
    }
  }
  const block=document.createElement("div");
  block.innerHTML=html;
  log.prepend(block);
  window.scrollTo({top:0,behavior:"smooth"});
}

go.addEventListener("click", ()=>{ ask(input.value); input.value=""; input.style.height="auto"; });
input.addEventListener("keydown", e=>{
  if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); ask(input.value); input.value=""; }
});
input.addEventListener("input", ()=>{ input.style.height="auto"; input.style.height=Math.min(input.scrollHeight,140)+"px"; });

const EXAMPLES=[
  "что такое меркантилизм",
  "когда началась Английская революция",
  "почему Реформация началась в Германии",
  "что такое абсолютизм",
  "кто такой Жан Кальвин",
  "что такое Великие географические открытия"
];
const chips=document.getElementById("chips");
for(const ex of EXAMPLES){
  const b=document.createElement("button");
  b.className="chip"; b.textContent=ex;
  b.addEventListener("click", ()=>ask(ex));
  chips.appendChild(b);
}
document.getElementById("stats").textContent =
  `${FRAGMENTS.length} фрагментов текста · работает без интернета`;
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
