"""Machine-translate extracted script units with any OpenAI-compatible chat endpoint.

  python tools/translate.py [--tags 00 02] [--endpoint URL] [--model NAME] [--limit N]

Reads work/text/<tag>.json (from extract.py), writes translation/en/<tag>.json as
{unit id: English markup}. Units already present in the output are skipped, so the run
can be stopped and resumed at any point; delete an entry to have it redone.

Markup handling: line breaks and the half-width indent space are layout only and are
dropped (build.py re-wraps); {NAME}/{SURNAME} pass through; keyword markers become
⟦...⟧ brackets the model must keep around the matching English words; other inline
instructions become ⟨n⟩ placeholders.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

JP_CHARS = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
KW = re.compile(r"\{kw:(\d+:\d+):([^}]*)\}")   # {kw:ID:FLAG:TEXT}; kid keeps "ID:FLAG"
OPTOK = re.compile(r"\{op:[0-9a-f]{4}:[0-9a-f]*\}")

PUNCT = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-",
    "…": "...", "　": " ", " ": " ", "！": "!", "？": "?", "，": ",",
    "「": '"', "」": '"', "『": '"', "』": '"', "（": "(", "）": ")",
    "～": "~", "〜": "~", "♪": "~", "☆": "*", "★": "*", "é": "e",
    "è": "e", "à": "a", "ï": "i", "ü": "u", "ö": "o",
})


def prepare(jp):
    """Japanese markup -> (prompt text, restore info)."""
    s = jp.replace("蝮", "").replace("㌻", "").replace("\n", "")
    ops = OPTOK.findall(s)
    for n, tok in enumerate(ops):
        s = s.replace(tok, f"⟨{n + 1}⟩", 1)
    kws = []
    while True:
        m = KW.search(s)
        if not m:
            break
        kid, word = m.group(1), m.group(2)
        rest = s[m.end():]
        if rest.startswith(word) and word:
            s = s[:m.start()] + "⟦" + word + "⟧" + rest[len(word):]
        else:
            s = s[:m.start()] + "⟦⟧" + rest
        kws.append(kid)
    return s, {"ops": ops, "kws": kws}


def balance_quotes(s, jp):
    """Repair the quote marks the model drops, doubles or adds around narration."""
    s = s.replace('\\"', '"')
    s = re.sub(r'",\s*$', '"', s)
    m = re.match(r'^(")?\s*\[[^\]]{1,60}\]\s*', s)   # echoed "[speaker]" tag
    if m:
        s = (m.group(1) or "") + s[m.end():]
    jp = jp.replace("\n", "").strip()
    opens = jp.startswith(("「", "『"))
    closes = jp.endswith(("」", "』"))
    if not opens and s.startswith('"') and s.endswith('"') and s.count('"') == 2:
        s = s[1:-1].strip()
    if opens and closes and '"' not in s:
        return f'"{s}"'
    if s.count('"') % 2 == 0:
        return s
    if s.endswith('"') and not closes:
        return s[:-1].rstrip()
    if s.startswith('"') and not opens:
        return s[1:].lstrip()
    if opens and not s.startswith('"'):
        return '"' + s
    return s + '"'


def restore(en, info, jp=""):
    """Model English -> build markup. Returns (markup, problems)."""
    problems = []
    s = en.translate(PUNCT).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\.{7,}", "......", s)   # long Japanese ellipses (each … is "...")
    s = balance_quotes(s, jp)
    for n, tok in enumerate(info["ops"]):
        ph = f"⟨{n + 1}⟩"
        if ph in s:
            s = s.replace(ph, tok, 1)
        else:
            s = s + tok
            problems.append(f"lost placeholder {ph}")
    parts = re.split(r"⟦([^⟧]*)⟧", s)
    out = [parts[0]]
    found = (len(parts) - 1) // 2
    for i in range(found):
        word, after = parts[1 + 2 * i], parts[2 + 2 * i]
        kid = info["kws"][i] if i < len(info["kws"]) else None
        out.append(f"{{kw:{kid}:{word}}}{word}" if kid else word)
        out.append(after)
    s = "".join(out)
    for kid in info["kws"][found:]:
        s = f"{{kw:{kid}:}}" + s
        problems.append("lost keyword bracket")
    s = s.replace("⟦", "").replace("⟧", "")
    s = re.sub(r"⟨\d+⟩", "", s)
    if JP_CHARS.search(s):
        problems.append("Japanese left in output")
    clean = "".join(ch for ch in s if _encodable(ch))
    if clean != s:
        problems.append(f"dropped unencodable {sorted(set(s) - set(clean))!r}")
    return clean, problems


def _encodable(ch):
    try:
        ch.encode("cp932")
        return True
    except UnicodeEncodeError:
        return False


def system_prompt(gl):
    names = "; ".join(f"{k} = {v}" for k, v in gl["terms"].items())
    return (
        f"You are translating the Japanese otome visual novel '{gl['game']}' (PSP) into "
        "natural, fluent, idiomatic English for a fan translation. Translate the meaning and "
        "tone, not word by word; dialogue should sound like real people talking.\n"
        + "\n".join(gl["style"]) + "\n"
        "Glossary (Japanese = English): " + names + ".\n"
        "Rules:\n"
        "- Japanese quote brackets 「」 become straight double quotes. Lines without 「」 are "
        "narration or thoughts: do not put quotes around them.\n"
        "- Do not repeat the [speaker] label in your output.\n"
        "- Keep {NAME} and {SURNAME} exactly as written; they are the player's given name and "
        "family name. When both appear together write {NAME} {SURNAME}.\n"
        "- Text inside ⟦ ⟧ is a dictionary keyword: put ⟦ ⟧ around the English words that "
        "translate it. Keep ⟨1⟩-style markers in place.\n"
        "- Use only plain ASCII punctuation (\", ', ..., -). No Japanese characters in the output.\n"
        "- 'quiz question' items are mythology quiz questions: translate as a short question or "
        "true/false statement (at most 90 characters). 'quiz answer' items are answer choices: "
        "a few words, at most 28 characters, no final period.\n"
        "- Output only a JSON array with exactly one English string per input item, in order."
    )


def speaker_label(gl, u):
    if u["kind"] == "choice":
        return "choice"
    if u["kind"] == "arg":
        return "title/system text"
    if u["kind"] == "quiz":
        return "quiz question"
    if u["kind"] == "quiz_choice":
        return "quiz answer"
    return gl["speakers"].get(str(u.get("speaker", 0)), f"speaker {u.get('speaker')}")


class Client:
    def __init__(self, endpoint, model, timeout=600):
        self.url = endpoint.rstrip("/") + "/chat/completions"
        self.model = model
        self.timeout = timeout

    def chat(self, system, user, temperature=0.3):
        body = {
            "model": self.model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            res = json.load(r)
        return res["choices"][0]["message"]["content"]


def parse_array(text, n):
    a, b = text.find("["), text.rfind("]")
    if (a < 0 or b < a) and n == 1 and text.strip():
        return [text.strip()]
    if a < 0 or b < a:
        raise ValueError(f"no JSON array in reply: {text[:200]!r}")
    arr = json.loads(text[a:b + 1])
    if isinstance(arr, list):
        arr = [next((v for v in x.values() if isinstance(v, str)), x) if isinstance(x, dict) else x
               for x in arr]
    if not isinstance(arr, list) or len(arr) != n or not all(isinstance(x, str) for x in arr):
        raise ValueError(f"expected {n} strings, got {len(arr) if isinstance(arr, list) else type(arr)}")
    return arr


def build_user(gl, batch, context):
    parts = []
    if context:
        ctx = [{"speaker": speaker_label(gl, u), "jp": prepare(u["jp"])[0], "en": en} for u, en in context]
        parts.append("Already translated, for context only (do not output these):\n"
                     + json.dumps(ctx, ensure_ascii=False, indent=0))
    items = [{"speaker": speaker_label(gl, u), "jp": prepare(u["jp"])[0]} for u in batch]
    parts.append(f"Translate the \"jp\" field of each of these {len(items)} items. Reply with a JSON "
                 f"array of exactly {len(items)} English strings, in order:\n"
                 + json.dumps(items, ensure_ascii=False, indent=0))
    return "\n\n".join(parts)


def strip_speaker(en, gl, u):
    """Drop a speaker name the model echoed in front of the line."""
    name = speaker_label(gl, u)
    for cand in {name, name.split(" (")[0], name.split(" ")[0]}:
        if cand and en.startswith(cand) and en[len(cand):len(cand) + 2].strip()[:1] in (":", "]", '"', ""):
            rest = en[len(cand):].lstrip(" :]")
            if rest:
                return rest
    return en


def translate_batch(client, gl, batch, context, retries=3):
    system = system_prompt(gl)
    user = build_user(gl, batch, context)
    last = None
    for attempt in range(retries):
        try:
            reply = client.chat(system, user, 0.3 + 0.2 * attempt)
            try:
                arr = parse_array(reply, len(batch))
            except json.JSONDecodeError:
                if len(batch) != 1:
                    raise
                arr = [reply.strip().strip("[]").strip()]
        except (ValueError, json.JSONDecodeError) as e:
            last = e
            continue
        results, bad = [], False
        for u, en in zip(batch, arr):
            en = strip_speaker(en.strip(), gl, u)
            markup, problems = restore(en, prepare(u["jp"])[1], u["jp"])
            if "Japanese left in output" in problems:
                bad = True
            results.append((markup, problems))
        if not bad or attempt == retries - 1:
            return results
        last = "bad characters in output"
    if len(batch) > 1:   # fall back to one line at a time
        out = []
        for i, u in enumerate(batch):
            out += translate_batch(client, gl, [u], context, retries)
        return out
    raise RuntimeError(f"giving up on {batch[0]['id']}: {last}")


def batches(units, size, max_chars):
    cur, chars, scene = [], 0, None
    for u in units:
        sc = u["id"].split("/")[0]
        if cur and (len(cur) >= size or chars + len(u["jp"]) > max_chars or sc != scene):
            yield cur
            cur, chars = [], 0
        cur.append(u)
        chars += len(u["jp"])
        scene = sc
    if cur:
        yield cur


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tags", nargs="*", default=None)
    ap.add_argument("--text", default=os.path.join(ROOT, "work", "text"))
    ap.add_argument("--out", default=os.path.join(ROOT, "translation", "en"))
    ap.add_argument("--glossary", default=os.path.join(ROOT, "data", "glossary.json"))
    ap.add_argument("--endpoint", default=os.environ.get("MT_ENDPOINT", "http://127.0.0.1:11435/v1"))
    ap.add_argument("--model", default=os.environ.get("MT_MODEL", "qwen3.6-35b-a3b-UD-Q4_K_M"))
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--max-chars", type=int, default=1200)
    ap.add_argument("--context", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="stop after N new units (0 = all)")
    a = ap.parse_args()

    with open(a.glossary, encoding="utf-8") as f:
        gl = json.load(f)
    os.makedirs(a.out, exist_ok=True)
    client = Client(a.endpoint, a.model)
    tags = a.tags or sorted(n[:-5] for n in os.listdir(a.text) if n.endswith(".json"))
    cache_path = os.path.join(os.path.dirname(a.text), "mt_cache.json")
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    problems_log = open(os.path.join(os.path.dirname(a.text), "mt_problems.log"), "a", encoding="utf-8")
    done_new = 0
    t0 = time.time()
    for tag in tags:
        with open(os.path.join(a.text, f"{tag}.json"), encoding="utf-8") as f:
            units = json.load(f)
        out_path = os.path.join(a.out, f"{tag}.json")
        out = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
        by_id = {u["id"]: u for u in units}
        todo = []
        for u in units:
            if u["id"] in out:
                continue
            if u["jp"] in cache:
                out[u["id"]] = cache[u["jp"]]
                continue
            todo.append(u)
        save(out_path, out)
        print(f"{tag}: {len(units)} units, {len(todo)} to translate", flush=True)
        prev_ids = [u["id"] for u in units]
        for batch in batches(todo, a.batch, a.max_chars):
            first = prev_ids.index(batch[0]["id"])
            ctx_ids = [i for i in prev_ids[max(0, first - a.context):first] if i in out]
            context = [(by_id[i], out[i]) for i in ctx_ids]
            try:
                results = translate_batch(client, gl, batch, context)
            except (RuntimeError, urllib.error.URLError, TimeoutError) as e:
                print(f"  batch at {batch[0]['id']} failed: {e}", flush=True)
                problems_log.write(f"{tag} {batch[0]['id']} FAILED {e}\n")
                continue
            for u, (markup, problems) in zip(batch, results):
                out[u["id"]] = markup
                cache[u["jp"]] = markup
                for p in problems:
                    problems_log.write(f"{tag} {u['id']} {p}\n")
            save(out_path, out)
            save(cache_path, cache)
            problems_log.flush()
            done_new += len(batch)
            rate = done_new / max(1e-9, time.time() - t0)
            print(f"  {tag} {batch[-1]['id']}: {len(out)}/{len(units)} ({rate:.1f} units/s)", flush=True)
            if a.limit and done_new >= a.limit:
                return
    problems_log.close()


if __name__ == "__main__":
    sys.exit(main())
