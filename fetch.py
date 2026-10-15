"""비공개 작업실 저장소(bichae-studio)의 drafts/<묶음번호>/ 사진·캡션을 이 실행 안에서만 잠깐 받는다(커밋하지 않음).
주소는 남이 짐작 못 하게 임의 이름 폴더로 만든다. 열쇠는 비밀 칸의 STUDIO_TOKEN(작업실 읽기 권한)만 쓴다.
  python fetch.py 묶음번호|"" site work → 사진은 site/<임의>/ (공개될 곳), 사진·캡션·번호는 work/ (공개 안 됨)"""
import json
import os
import re
import secrets
import sys
import urllib.request
from pathlib import Path

STUDIO = "butonco00-ux/bichae-studio"


def get(path, raw=False):
    req = urllib.request.Request(f"https://api.github.com/repos/{STUDIO}/contents/{path}",
                                 headers={"Authorization": "Bearer " + os.environ["STUDIO_TOKEN"].strip(),
                                          "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=60).read()


def main():
    sid, out, work = sys.argv[1].strip(), Path(sys.argv[2]), Path(sys.argv[3])
    if not os.environ.get("STUDIO_TOKEN", "").strip():
        sys.exit("❌ 작업실 권한 열쇠(STUDIO_TOKEN)가 비밀 칸에 없어요")
    sid = sid or get("drafts/latest.txt", raw=True).decode().strip()
    if not re.fullmatch(r"\d{8}-\d{6}", sid):
        sys.exit("❌ 묶음 번호 모양이 아니에요. 텔레그램에 온 번호(예: 20261016-173012)를 그대로 넣어 주세요")
    name = secrets.token_hex(12)
    d = out / name
    d.mkdir(parents=True)
    work.mkdir(parents=True)
    files = [f["name"] for f in json.loads(get(f"drafts/{sid}")) if re.fullmatch(r"\d\d\.jpg|caption\.txt", f["name"])]
    for f in files:
        data = get(f"drafts/{sid}/{f}", raw=True)
        (work / f).write_bytes(data)
        if f.endswith(".jpg"):   # 공개 주소에는 사진만(캡션·번호는 올리지 않음)
            (d / f).write_bytes(data)
    (work / "id.txt").write_text(sid, encoding="utf-8")
    (out / "index.html").write_text("", encoding="utf-8")
    print(f"묶음 {sid}: 사진 {sum(f.endswith('.jpg') for f in files)}장 받음")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as g:
        print(f"name={name}", file=g)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
