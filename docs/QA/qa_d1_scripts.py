"""DPL-153/157 QA-D1 独立行为级验证脚本（t_69960b58）。

QA 自写脚本，驱动被测函数行为（非研发测试追认）。被测代码只读：
/workspace/InfoManager（main @ 2c21d6f）。运行: python3 qa_d1_scripts.py
"""
import json
import sqlite3
import sys
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

INFO = Path("/workspace/InfoManager")
sys.path.insert(0, str(INFO))
sys.path.insert(0, str(INFO / "scripts"))
sys.path.insert(0, str(INFO / "tests"))  # conftest fixtures 不是本脚本依赖，仅路径

import scripts.process_collection as pcm  # noqa: E402
import scripts.pipeline_state as psm  # noqa: E402

RESULTS = []


def check(tc, desc, fn):
    try:
        detail = fn()
        RESULTS.append((tc, desc, "PASS", detail or ""))
    except AssertionError as e:
        RESULTS.append((tc, desc, "FAIL", str(e)))
    except Exception as e:
        RESULTS.append((tc, desc, "ERROR", f"{e}\n{traceback.format_exc()[-400:]}"))


# ── TC-Q1: R1 pipeline_state 真实 SQLite 往返 + fail-open ─────────────
def tc_q1():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ps.db"
        old_db = psm.DB_PATH
        psm.DB_PATH = db
        try:
            psm.init_db()
            psm.start_run("trace_q1", "raw input for tc-q1")
            assert psm.record_inbound_message_id("trace_q1", "om_q1_real") is True
            assert psm.get_inbound_message_id("trace_q1") == "om_q1_real"
            assert psm.get_inbound_message_id("trace_missing") == ""  # 空记录
        finally:
            psm.DB_PATH = old_db
    return "real sqlite roundtrip ok"


# ── TC-Q2: D1 CLI 参数优先级最高 ───────────────────────────────────────
def tc_q2():
    old_cli, old_state = pcm.CLI_MESSAGE_ID, pcm.pipeline_state
    old_enabled = pcm._PIPELINE_STATE_ENABLED
    try:
        ps = MagicMock()
        ps.get_inbound_message_id.return_value = "om_from_state"
        pcm.CLI_MESSAGE_ID = "om_from_cli"
        pcm.pipeline_state = ps
        pcm._PIPELINE_STATE_ENABLED = True
        fetched = []
        orig_fetch, orig_gate = pcm.fetch_card_url_from_feishu, pcm.validate_recovered_url
        pcm.fetch_card_url_from_feishu = lambda mid: fetched.append(mid) or ""
        pcm.validate_recovered_url = lambda *a, **k: (True, 0.99) if a and a[-1] is True or k else True
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "p.jsonl"
            pcm.LOG_PATH, pcm.LOG_DIR = log, Path(td)
            pcm.send_feishu_msg = lambda t: True
            pcm._recover_url_by_search = lambda t: ""
            pcm.process("今日头条【研究生导师避坑指南：如何挑选靠谱导师的十个实战要点与避坑经验总结】打开今日头条APP查看更多精彩内容")
        pcm.fetch_card_url_from_feishu = orig_fetch
        pcm.validate_recovered_url = orig_gate
        assert fetched and fetched[0] == "om_from_cli", f"fetch got {fetched}"
        return "fetch received CLI om_id"
    finally:
        pcm.CLI_MESSAGE_ID, pcm.pipeline_state = old_cli, old_state
        pcm._PIPELINE_STATE_ENABLED = old_enabled


# ── TC-Q3: gateway.log 三分支 ─────────────────────────────────────────
def tc_q3():
    now = datetime.now()
    old = pcm._GATEWAY_LOG_PATH
    try:
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "g.log"
            pcm._GATEWAY_LOG_PATH = str(log)
            # 多条 → 空
            ts = now.strftime("%Y-%m-%d %H:%M:%S")
            log.write_text(f"{ts} inbound message_id=om_aaa\n{ts} inbound message_id=om_bbb\n")
            assert pcm.scan_gateway_log_for_message_ids() == set(), "多条必须不猜"
            # 唯一 → 返回
            log.write_text(f"{ts} inbound message_id=om_only\n")
            assert pcm.scan_gateway_log_for_message_ids() == {"om_only"}
            # 窗外旧时间戳 → 空
            old_ts = (now - timedelta(seconds=3600)).strftime("%Y-%m-%d %H:%M:%S")
            log.write_text(f"{old_ts} inbound message_id=om_stale\n")
            assert pcm.scan_gateway_log_for_message_ids(window_seconds=300) == set()
    finally:
        pcm._GATEWAY_LOG_PATH = old
    return "multi=refuse / single=trust / stale=reject"


# ── TC-Q4: R2 相似度闸门 fail-closed ──────────────────────────────────
def tc_q4():
    share = "深度解析大模型Agent技术落地实践指南"
    url = "https://www.toutiao.com/article/7400000000000000123/"
    og = ('<html><head><meta property="og:title" content="%s"></head></html>' % share).encode()
    old = pcm.urllib.request.urlopen
    try:
        class R:
            def __init__(s, b): s.b = b
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return s.b
        pcm.urllib.request.urlopen = lambda req, timeout=None: R(og)
        ok, dice = pcm.validate_recovered_url(share, url, _return_dice=True)
        assert ok and dice >= 0.6, f"高相似应放行 got {ok},{dice}"
        bad = ('<html><head><meta property="og:title" content="周末露营攻略"></head></html>').encode()
        pcm.urllib.request.urlopen = lambda req, timeout=None: R(bad)
        ok2, dice2 = pcm.validate_recovered_url(share, url, _return_dice=True)
        assert not ok2, "无关标题必须拒绝"
        def raise_(*a, **k): raise OSError("blocked")
        pcm.urllib.request.urlopen = raise_
        assert pcm.validate_recovered_url(share, url) is False, "网络失败 fail-closed"
        pcm.urllib.request.urlopen = lambda req, timeout=None: R(b"<html><head></head></html>")
        assert pcm.validate_recovered_url(share, url) is False, "无 og:title fail-closed"
    finally:
        pcm.urllib.request.urlopen = old
    return "high=True unrelated/fetch-fail/no-og=False"


# ── TC-Q5: R3 url_missing 诚实降级（驱动 process()）───────────────────
def tc_q5():
    with tempfile.TemporaryDirectory() as td:
        old = {k: getattr(pcm, k) for k in
               ("LOG_PATH", "LOG_DIR", "_PIPELINE_STATE_ENABLED", "pipeline_state",
                "CLI_MESSAGE_ID", "send_feishu_msg", "git_push", "_recover_url_by_search",
                "scan_gateway_log_for_message_ids", "fetch_card_url_from_feishu")}
        try:
            pcm.LOG_PATH = Path(td) / "p.jsonl"
            pcm.LOG_DIR = Path(td)
            pcm._PIPELINE_STATE_ENABLED = False
            pcm.CLI_MESSAGE_ID = ""
            pcm.pipeline_state = MagicMock()
            pcm.send_feishu_msg = lambda t: True
            pcm.git_push = lambda fp, new_tags=None, is_merge=False: True
            pcm._recover_url_by_search = lambda t: ""
            pcm.scan_gateway_log_for_message_ids = lambda window_seconds=300: set()
            pcm.fetch_card_url_from_feishu = lambda mid: ""
            captured = {}
            def fake_wtv(title, url, classification, summary_data, status, plat, **kw):
                captured.update(cls=classification, summary=summary_data, status=status)
                return (str(Path(td) / "entry.md"), False)
            pcm.write_to_vault = fake_wtv
            res = pcm.process("今日头条【研究生导师避坑指南：如何挑选靠谱导师的十个实战要点与避坑经验总结】打开今日头条APP查看更多精彩内容")
            assert res["status"] == "url_missing", f"status={res['status']}"
            assert res["extraction_status"] == "failed"
            assert captured["cls"].get("ocr_skipped_reason") == "url_missing", captured
            assert captured["cls"].get("url_source") == "none"
            assert "链接反查失败" in captured["summary"].get("summary", "")
            assert captured["status"] == "failed"
            entries = [json.loads(l) for l in pcm.LOG_PATH.read_text().splitlines() if l.strip()]
            missing = [e for e in entries if e.get("status") == "url_missing"]
            assert missing and missing[0]["message"].startswith("ocr_skipped:"), missing
        finally:
            for k, v in old.items():
                setattr(pcm, k, v)
    return "meta fields + ocr_skipped log + failed status"


# ── TC-Q6: R4 fail-open（AC7）─────────────────────────────────────────
def tc_q6():
    with tempfile.TemporaryDirectory() as td:
        old_vp = pcm.VAULT_PATH
        pcm.VAULT_PATH = Path(td)
        old_urlopen, old_which = pcm.urllib.request.urlopen, pcm.shutil.which
        try:
            def raise_(*a, **k): raise OSError("blocked")
            pcm.urllib.request.urlopen = raise_
            pcm.shutil.which = lambda name: None
            out = pcm._headless_toutiao_ocr_fallback("https://www.toutiao.com/w/7400000000000000900/")
            assert out["ok"] is False and out["ocr_status"] == "failed" and out["text"] == ""
        finally:
            pcm.VAULT_PATH = old_vp
            pcm.urllib.request.urlopen, pcm.shutil.which = old_urlopen, old_which
    return "all-channels-down → ok=False, no raise"


# ── TC-Q7: R4 状态机 ok/partial（AC6 逻辑面）──────────────────────────
def tc_q7():
    from PIL import Image
    import io
    with tempfile.TemporaryDirectory() as td:
        old_vp = pcm.VAULT_PATH
        pcm.VAULT_PATH = Path(td)
        old_urlopen, old_ocr = pcm.urllib.request.urlopen, pcm.ocr_image_chinese
        try:
            def img():
                b = io.BytesIO()
                Image.new("RGB", (40, 40), "white").save(b, format="JPEG")
                return b.getvalue()
            payload = json.dumps({"data": {"title": "", "content":
                "".join('<div class="pgc-img"><img src="https://p3-sign.toutiaoimg.com/x/%d.jpg"></div>' % i
                        for i in range(3))}}).encode()

            class R:
                def __init__(s, b): s.b = b
                def __enter__(s): return s
                def __exit__(s, *a): return False
                def read(s): return s.b

            def fake_uo(req, timeout=None):
                if "/api/pc/detail/" in req.full_url:
                    return R(payload)
                return R(img())
            pcm.urllib.request.urlopen = fake_uo
            pcm.ocr_image_chinese = lambda p: "识别到的图片文字内容"
            out = pcm._headless_toutiao_ocr_fallback("https://www.toutiao.com/w/7400000000000000900/")
            assert out["ok"] and out["ocr_status"] == "ok" and out["image_count"] == 3
            assert "识别到的图片文字内容" in out["text"]
            # partial: 1/3 OCR 失败
            calls = {"n": 0}
            def half(p):
                calls["n"] += 1
                return "文字" if calls["n"] == 1 else ""
            pcm.ocr_image_chinese = half
            out2 = pcm._headless_toutiao_ocr_fallback("https://www.toutiao.com/w/7400000000000000901/")
            assert out2["ocr_status"] == "partial" and out2["ok"], out2
        finally:
            pcm.VAULT_PATH = old_vp
            pcm.urllib.request.urlopen, pcm.ocr_image_chinese = old_urlopen, old_ocr
    return "ok(3/3) + partial(1/3) + text merge"


if __name__ == "__main__":
    check("TC-Q1", "R1 pipeline_state 真实 SQLite 往返+fail-open", tc_q1)
    check("TC-Q2", "ARCH D1 CLI 参数优先级最高", tc_q2)
    check("TC-Q3", "AC2 gateway.log 多条不猜/唯一采信/窗外拒绝", tc_q3)
    check("TC-Q4", "R2/AC4 闸门 fail-closed 全分支", tc_q4)
    check("TC-Q5", "R3/AC5 url_missing 诚实降级", tc_q5)
    check("TC-Q6", "R4/AC7 fail-open 无 silent success", tc_q6)
    check("TC-Q7", "R4/AC6 逻辑面 ok/partial 状态机", tc_q7)
    fails = 0
    for tc, desc, verdict, detail in RESULTS:
        print(f"[{verdict}] {tc} {desc}" + (f" — {detail.splitlines()[0] if detail.splitlines() else '(no detail)'}" if verdict != "PASS" else f" — {detail}"))
        if verdict != "PASS":
            fails += 1
            print("      " + detail.replace("\n", "\n      "))
    print(f"\nSUMMARY: {len(RESULTS) - fails}/{len(RESULTS)} PASS, {fails} FAIL/ERROR")
    sys.exit(1 if fails else 0)
