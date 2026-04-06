"""
Local mini-dashboard: pipeline status, metrics snapshot, autonomous PID, start/stop hints.
Run: python src/dashboard_server.py --base-dir .
Open: http://127.0.0.1:8765/
"""
from __future__ import annotations

import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from env_loader import load_autonomous_env
from process_util import is_process_running


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _tail_csv_metrics(path: Path, max_rows: int = 25) -> Dict[str, Any]:
    ensure_metrics_csv = path.exists()
    if not ensure_metrics_csv:
        return {"rows": [], "totals": {}}
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    tail = rows[-max_rows:] if len(rows) > max_rows else rows
    revenue = sum(float(r.get("revenue_usd") or 0) for r in rows)
    views = sum(float(r.get("views") or 0) for r in rows)
    return {"rows": tail, "totals": {"row_count": len(rows), "views_sum": views, "revenue_usd_sum": round(revenue, 4)}}


def build_status_payload(base_dir: Path) -> Dict[str, Any]:
    pipeline = _read_json(base_dir / "output" / "pipeline_report.json")
    autonomous = _read_json(base_dir / "output" / "autonomous_report.json")
    state = _read_json(base_dir / "data" / "autonomous_state.json")
    drop_summary = _read_json(base_dir / "output" / "drop_for_manual_upload" / "_summary.json")
    metrics = _tail_csv_metrics(base_dir / "data" / "metrics" / "daily_metrics.csv")

    pid_path = base_dir / "data" / "autonomous.pid"
    pid_info: Dict[str, Any] = {"path": str(pid_path), "pid": None, "running": False}
    if pid_path.exists():
        try:
            pid = int((pid_path.read_text(encoding="utf-8") or "0").strip().splitlines()[0])
            pid_info["pid"] = pid
            pid_info["running"] = is_process_running(pid)
        except (ValueError, IndexError):
            pass

    return {
        "pipeline_report": pipeline,
        "autonomous_report": autonomous,
        "autonomous_state": state,
        "drop_summary": drop_summary,
        "metrics": metrics,
        "pid": pid_info,
        "paths": {
            "latest_video": str(base_dir / "output" / "drop_for_manual_upload" / "latest" / "video.mp4"),
            "manual_drop": str(base_dir / "output" / "drop_for_manual_upload"),
        },
    }


# Commands shown even if JS fails (no nullish coalescing in HTML — older browsers parse inline script safely).
_CMD_ONCE = "python src/autonomous_service.py --base-dir . --monthly-fixed-cost 50 --enable-upload-hook --enable-metrics-hook"
_CMD_LOOP = (
    "python src/autonomous_service.py --base-dir . --loop --interval-seconds 86400 "
    "--enable-upload-hook --enable-metrics-hook --pid-file data/autonomous.pid"
)
_CMD_STOP = "python src/stop_autonomous.py --base-dir ."
_CMD_ONE = "python src/main.py --base-dir . --script-max-items 1"

HTML_PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>VideoAutomation</title>
  <style>
    :root {{ --bg:#0f1419; --card:#1a2332; --text:#e7ecf3; --muted:#8b9aab; --accent:#3d8bfd; --ok:#3fb950; --warn:#d29922; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; line-height: 1.5; }}
    h1 {{ font-size: 1.35rem; margin: 0 0 8px; }}
    p.sub {{ color: var(--muted); margin: 0 0 24px; font-size: 0.95rem; }}
    .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
    .card {{ background: var(--card); border-radius: 12px; padding: 16px 18px; border: 1px solid #2d3a4d; }}
    .card h2 {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin: 0 0 12px; }}
    .stat {{ font-size: 1.6rem; font-weight: 600; }}
    .pill {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }}
    .pill.ok {{ background: rgba(63,185,80,0.15); color: var(--ok); }}
    .pill.bad {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    pre.cmd {{ background: #0d1117; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 0.8rem; border: 1px solid #30363d; white-space: pre-wrap; word-break: break-all; min-height: 2.5rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th, td {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid #2d3a4d; }}
    th {{ color: var(--muted); font-weight: 500; }}
    a {{ color: var(--accent); }}
    .muted {{ color: var(--muted); font-size: 0.85rem; }}
    .err {{ color: #f85149; margin-top: 8px; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>VideoAutomation</h1>
  <p class="sub">Local status · refresh the page to update · <span id="ts">loading…</span></p>
  <p id="load-err" class="err" style="display:none"></p>

  <div class="grid" id="cards"></div>

  <div class="card" style="margin-top:16px">
    <h2>Start / stop autonomous service</h2>
    <p class="muted">Copy a command into PowerShell from the repo root. Loop keeps running until you stop it or close the window.</p>
    <p><strong>One cycle (test)</strong></p>
    <pre class="cmd" id="cmd-once">{_CMD_ONCE}</pre>
    <p><strong>Loop (stay active — uses PID file)</strong></p>
    <pre class="cmd" id="cmd-loop">{_CMD_LOOP}</pre>
    <p><strong>Stop loop</strong></p>
    <pre class="cmd" id="cmd-stop">{_CMD_STOP}</pre>
    <p><strong>First video only (smoke test)</strong></p>
    <pre class="cmd" id="cmd-one">{_CMD_ONE}</pre>
  </div>

  <div class="card" style="margin-top:16px">
    <h2>Recent metrics (daily_metrics.csv)</h2>
    <div id="metrics-wrap"><p class="muted">Loading…</p></div>
  </div>

  <script src="/dashboard.js" defer></script>
</body>
</html>
"""

# No `??` (nullish coalescing) — unsupported in older Edge/embedded WebViews.
DASHBOARD_JS = """
(function () {
  function el(id) { return document.getElementById(id); }
  function numOrDash(v) {
    if (v === null || v === undefined) return "\\u2014";
    if (typeof v === "number" && !isNaN(v)) return String(v);
    return String(v);
  }
  function gapMoney(be) {
    if (!be || be.gap_to_break_even_usd === null || be.gap_to_break_even_usd === undefined) return "\\u2014";
    return "$" + String(be.gap_to_break_even_usd);
  }
  function dropCount(ds) {
    if (!ds || ds.videos_copied === null || ds.videos_copied === undefined) return "0";
    return String(ds.videos_copied);
  }
  async function load() {
    var errEl = el("load-err");
    try {
      var r = await fetch("/api/status");
      if (!r.ok) throw new Error("HTTP " + r.status);
      var d = await r.json();
      if (errEl) { errEl.style.display = "none"; errEl.textContent = ""; }

      el("ts").textContent = new Date().toISOString();

      var pr = d.pipeline_report || {};
      var be = pr.break_even || {};
      var pid = d.pid || {};
      var pidLabel;
      if (pid.pid !== null && pid.pid !== undefined) {
        pidLabel = pid.running
          ? '<span class="pill ok">PID ' + pid.pid + " running</span>"
          : '<span class="pill bad">PID ' + pid.pid + " not running</span>";
      } else {
        pidLabel = '<span class="pill bad">No PID file (loop not started)</span>';
      }

      var lastAuto = (d.autonomous_report && d.autonomous_report.generated_at) || "\\u2014";
      var pathLatest = (d.paths && d.paths.latest_video) ? d.paths.latest_video : "";

      var cards = el("cards");
      cards.innerHTML =
        '<div class="card"><h2>Pipeline</h2>' +
        '<div class="stat">' + numOrDash(pr.scripts_count) + "</div>" +
        '<div class="muted">Scripts this run</div></div>' +
        '<div class="card"><h2>Renders</h2>' +
        '<div class="stat">' + numOrDash(pr.render_jobs_count) + "</div>" +
        '<div class="muted">FFmpeg jobs</div></div>' +
        '<div class="card"><h2>Upload queue</h2>' +
        '<div class="stat">' + numOrDash(pr.uploads_ready) + "</div>" +
        '<div class="muted">YouTube ready</div></div>' +
        '<div class="card"><h2>Break-even gap</h2>' +
        '<div class="stat">' + gapMoney(be) + "</div>" +
        '<div class="muted">Revenue vs cost (see CSV)</div></div>' +
        '<div class="card"><h2>Autonomous</h2>' +
        '<div style="margin-top:8px">' + pidLabel + "</div>" +
        '<div class="muted" style="margin-top:8px">Last report: ' + lastAuto + "</div></div>" +
        '<div class="card"><h2>Manual drop</h2>' +
        '<div class="stat">' + dropCount(d.drop_summary) + "</div>" +
        '<div class="muted">Videos copied · latest path below</div>' +
        '<div class="muted" style="margin-top:8px;font-size:0.75rem">' +
        pathLatest.replace(/</g, "&lt;") +
        "</div></div>";

      var m = d.metrics || {};
      var rows = m.rows || [];
      var mw = el("metrics-wrap");
      if (!rows.length) {
        mw.innerHTML =
          '<p class="muted">No rows yet. Run metrics import after uploads, or append CSV manually.</p>';
      } else {
        var cols = Object.keys(rows[0]);
        var thead = "<thead><tr>";
        for (var i = 0; i < cols.length; i++) {
          thead += "<th>" + String(cols[i]).replace(/</g, "&lt;") + "</th>";
        }
        thead += "</tr></thead>";
        var tbody = "<tbody>";
        for (var ri = rows.length - 1; ri >= 0; ri--) {
          var row = rows[ri];
          tbody += "<tr>";
          for (var j = 0; j < cols.length; j++) {
            var cell = row[cols[j]];
            tbody += "<td>" + String(cell !== undefined && cell !== null ? cell : "").replace(/</g, "&lt;") + "</td>";
          }
          tbody += "</tr>";
        }
        tbody += "</tbody>";
        mw.innerHTML =
          "<table>" +
          thead +
          tbody +
          "</table>" +
          '<p class="muted" style="margin-top:12px">Totals: ' +
          JSON.stringify(m.totals || {}) +
          "</p>";
      }
    } catch (e) {
      if (errEl) {
        errEl.style.display = "block";
        errEl.textContent =
          "Could not load /api/status. Run: python src/dashboard_server.py --base-dir . from the repo root. (" +
          (e && e.message ? String(e.message) : String(e)) +
          ")";
      }
      el("metrics-wrap").innerHTML =
        '<p class="muted">Fix the error above; metrics load from the same API.</p>';
    }
  }
  load();
  setInterval(load, 60000);
})();
"""


class Handler(BaseHTTPRequestHandler):
    base_dir: Path = _repo_root()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            payload = build_status_payload(self.base_dir)
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/dashboard.js":
            body = DASHBOARD_JS.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Local dashboard for VideoAutomation")
    p.add_argument("--base-dir", default=".", help="Project root")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.base_dir).resolve()
    load_autonomous_env(root)
    Handler.base_dir = root
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Dashboard: http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
