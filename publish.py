"""인스타에 올리기(GitHub 에서 수동 실행 전용). 비채 카드 묶음 한 개 = 캐러셀 한 개.
클로드테스트/cardnews/engine/instagram.py·publish.py 의 순서와 확인 절차를 옮긴 것(2026-10-11). 열쇠는 옮기지 않았다:
이 저장소 비밀 보관함의 IG_ACCESS_TOKEN 만 쓴다.

  python publish.py --dir site/<임의이름> --base https://.../<임의이름> --mode 연습|실제 --confirm 올립니다
2026-10-15 바뀜(사장님: "사진은 인스타 올릴 때만 공개했다가 올리고 나면 완전 삭제, 기록도 안 남게"):
  사진은 비공개 작업실 저장소에 있고, post.yml 이 잠깐 받아 공개 주소(Pages)로 내놓았다가 게시 뒤 빈 페이지로 덮는다.
  이 저장소에는 사진·캡션·올린 기록을 커밋하지 않는다. 같은 글을 두 번 올리지 않는 확인은 인스타 최근 게시물의 캡션으로 한다.

확인된 것(cardnews 문서, 2026-09-17): Instagram 로그인 방식 = graph.instagram.com, 사진은 공개 주소의 JPEG(8MB 이하, 4:5~1.91:1),
캐러셀 2~10장, 사진마다 media(is_carousel_item) → media(CAROUSEL) → status_code FINISHED 대기 → media_publish."""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://graph.instagram.com/v25.0"
WORD = "올립니다"


def say(msg):
    print(msg, flush=True)


def call(method, path, token, **params):
    params["access_token"] = token
    data = urllib.parse.urlencode(params)
    url = f"{BASE}/{path}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url + ("?" + data if method == "GET" else ""), data=None if method == "GET" else data.encode(), method=method)
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode()).get("error", {})
            except ValueError:
                err = {}
            if err.get("code") == 190:
                raise SystemExit("❌ 인스타 열쇠(토큰)가 만료됐거나 잘못됐어요. 새로 받아 비밀 보관함에 넣어 주세요")
            if err.get("code") in (1, 2, 4, 17, 32, 613) and attempt < 2:   # 일시적 오류·호출 한도
                time.sleep(10 * (attempt + 1))
                continue
            msg = (err.get("error_user_msg") or err.get("message") or f"HTTP {e.code}").replace(token, "***")
            msg += f" (code {err.get('code')}, subcode {err.get('error_subcode')}, 단계 {path.split('/')[-1]})"
            raise SystemExit(f"❌ 인스타가 거절했어요: {msg}")
        except urllib.error.URLError:
            if attempt == 2:
                raise SystemExit("❌ 인스타 서버에 연결하지 못했어요")
            time.sleep(3 * (attempt + 1))


def wait(cid, token, limit=300):
    start = time.time()
    while True:
        st = call("GET", cid, token, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED") or time.time() - start > limit:
            raise SystemExit(f"❌ 인스타가 사진을 처리하지 못했어요(상태: {st})")
        time.sleep(5)


def wait_pages(urls, files, limit=600):
    """공개 주소의 사진이 방금 올린 파일과 같은지 확인(반영이 늦으면 기다린다)."""
    start = time.time()
    while True:
        left = 0
        for u, f in zip(urls, files):
            try:
                left += urllib.request.urlopen(u, timeout=30).read() != f.read_bytes()
            except (urllib.error.URLError, OSError):
                left += 1
        if not left:
            return
        if time.time() - start > limit:
            raise SystemExit("❌ 카드 사진이 공개 주소에 아직 안 올라왔어요. 5분 뒤 다시 실행해 주세요")
        say(f"공개 주소 반영 기다리는 중… ({left}장 남음)")
        time.sleep(20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--mode", default="연습")
    ap.add_argument("--confirm", default="")
    a = ap.parse_args()
    mode = a.mode.strip()
    folder = Path(a.dir)
    sid = (folder / "id.txt").read_text(encoding="utf-8").strip() if (folder / "id.txt").exists() else folder.name
    files = sorted(folder.glob("[0-9][0-9].jpg"))
    cap = (folder / "caption.txt").read_text(encoding="utf-8").strip() if (folder / "caption.txt").exists() else ""
    problems = []
    if not folder.is_dir():
        problems.append("묶음을 찾지 못했어요. 텔레그램에 온 번호를 그대로 넣어 주세요")
    elif not 2 <= len(files) <= 10:
        problems.append(f"사진이 {len(files)}장이에요. 인스타 묶음은 2~10장이어야 해요")
    if not cap:
        problems.append("캡션이 비어 있어요")
    if len(cap) > 2200:
        problems.append(f"캡션이 {len(cap)}자예요. 2,200자까지 돼요")
    if mode not in ("연습", "실제"):
        problems.append("모드는 '연습' 또는 '실제'로 골라 주세요")
    if mode == "실제" and a.confirm.strip() != WORD:
        problems.append(f"실제로 올리려면 확인 칸에 '{WORD}'라고 적어 주세요")
    if problems:
        for p in problems:
            say("❌ " + p)
        return 1
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        say("❌ 인스타 열쇠(IG_ACCESS_TOKEN)가 비밀 보관함에 없어요")
        return 1
    me = call("GET", "me", token, fields="user_id,username")
    uid = str(me.get("user_id") or me.get("id") or "")
    q = (call("GET", f"{uid}/content_publishing_limit", token, fields="quota_usage,config").get("data") or [{}])[0]
    say(f"인스타 연결 정상: @{me.get('username', '')} · 오늘 게시 {q.get('quota_usage', 0)}/{(q.get('config') or {}).get('quota_total', 100)}")
    recent = call("GET", f"{uid}/media", token, fields="caption", limit="10").get("data") or []
    if any((m.get("caption") or "").strip() == cap for m in recent):
        say("❌ 같은 캡션의 글이 이미 인스타에 있어요. 두 번 올리지 않았어요")
        return 1
    urls = [f"{a.base.rstrip('/')}/{f.name}" for f in files]
    if mode == "연습":
        say(f"✅ 연습 모드: 실제로는 올리지 않았어요. 묶음 {sid}, 사진 {len(files)}장, 캡션 {len(cap)}자")
        say("올라갈 계정이 위의 @이름이 맞는지 꼭 확인해 주세요.")
        return 0
    wait_pages(urls, files)
    kids = []
    for i, u in enumerate(urls, 1):
        kids.append(call("POST", f"{uid}/media", token, image_url=u, is_carousel_item="true")["id"])
        say(f"사진 {i}/{len(urls)} 준비")
    for k in kids:
        wait(k, token)
    say("단계: 사진 처리 완료 → 묶음 만들기")   # 2026-10-14 어느 단계에서 '서버 내부 오류'가 나는지 재려고 넣음
    car = call("POST", f"{uid}/media", token, media_type="CAROUSEL", children=",".join(kids), caption=cap)["id"]
    say("단계: 묶음 만들기 완료 → 처리 대기")
    wait(car, token)
    say("단계: 처리 완료 → 게시")
    # 2026-10-14 확인: 인스타가 '서버 내부 오류(subcode 2207085)'를 돌려줘도 실제로는 올라가 있었다(사장님이 앱에서 확인).
    #   그래서 실패로 끝내기 전에 계정의 가장 최근 게시물을 보고, 방금(10분 안) 올라간 것이 있으면 성공으로 기록한다.
    #   틀린 추측이었던 것: "실패했으니 다시 올리자" → 같은 글이 여러 번 올라갔다.
    try:
        mid = call("POST", f"{uid}/media_publish", token, creation_id=car)["id"]
    except SystemExit as e:
        import datetime
        last = (call("GET", f"{uid}/media", token, fields="id,timestamp,permalink", limit="1").get("data") or [{}])[0]
        ts = last.get("timestamp", "")
        try:
            age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")).total_seconds()
        except ValueError:
            age = 1e9
        if age > 600:
            raise
        say(f"인스타가 오류를 돌려줬지만 방금 올라간 게시물이 있어요({int(age)}초 전). 올라간 것으로 기록합니다.")
        mid = last["id"]
    link = call("GET", mid, token, fields="permalink").get("permalink", "")
    say(f"✅ 인스타에 올렸어요 {link}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
