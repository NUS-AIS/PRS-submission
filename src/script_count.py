"""Word count of the English (spoken) lines of a bilingual script, per slide and per speaker."""
import re
import sys


def spoken(body):
    lines = [l for l in body.splitlines() if l.strip() and not l.startswith(">") and not l.startswith("KEY:")]
    return re.sub(r"\[[^\]]*\]", "", " ".join(lines))  # [stage cues] are not spoken


def parse(text):
    out = []
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        head, body = sec.split("\n", 1)
        m = re.match(r"Slide (\d+) · Speaker (\w)", head)
        out.append((int(m.group(1)), m.group(2), body.strip()))
    return out


if __name__ == "__main__":
    sects = parse(open(sys.argv[1], encoding="utf-8").read())
    per = {}
    for n, spk, body in sects:
        w = len(spoken(body).split())
        per[spk] = per.get(spk, 0) + w
        print(n, spk, w)
    print(per, sum(per.values()))
