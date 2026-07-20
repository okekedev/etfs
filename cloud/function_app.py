"""Sigma-bet scanner — Azure Functions (Python v2 model).

Timers (UTC; ET = UTC-4 in summer):
  scan_cycle : every 2h market hours (9:45a-3:45p ET) — refreshes the dashboard
               only; no emails.
  eod_update : ~4:30a ET every day — builds the flat-file data (when a new one
               exists) and sends the ONE daily email (consolidated digest: ETF
               reversion + microcap flow + crypto). On weekends/holidays there is
               no new options/ETF data, but crypto (24/7) still updates daily.

HTTP:
  GET /api/run?job=scan|eod|brief  (function key) — manual kick for testing
"""
import logging
import azure.functions as func
from scanner import core

app = func.FunctionApp()

@app.timer_trigger(schedule="0 45 13,15,17,19 * * 1-5", arg_name="timer", run_on_startup=False)
def scan_cycle(timer: func.TimerRequest) -> None:
    result = core.run_scan()
    logging.info("scan_cycle: %s", result)

# EOD build + the single daily email at ~4:30a ET, EVERY day, after the OPRA flat
# file publishes (observed 11:45p-3:30a ET; 4:30 clears it with self-healing
# retries for late files). Fires at BOTH DST-candidate UTC times (08:30=EDT,
# 09:30=EST); run_eod is idempotent and sends the consolidated digest (ETF
# reversion + microcap flow + crypto) via send_brief's Central-hour gate, so
# exactly one email lands at ~4:30a ET (3:30a CT) year-round. On weekends/holidays
# there is no new options/ETF flat file (run_eod just finds nothing to build), but
# crypto trades 24/7 so its signals still refresh. This is the only email sent.
@app.timer_trigger(schedule="0 30 8,9 * * *", arg_name="timer", run_on_startup=False)
def eod_update(timer: func.TimerRequest) -> None:
    result = core.run_eod()
    logging.info("eod_update: %s", result)

@app.route(route="run", auth_level=func.AuthLevel.FUNCTION)
def run_manual(req: func.HttpRequest) -> func.HttpResponse:
    job = req.params.get("job", "scan")
    if job == "eod":
        result = core.run_eod()
    elif job == "brief":
        result = core.send_brief(req.params.get("tag", "am"), force=True)
    else:
        result = core.run_scan()
    return func.HttpResponse(result, status_code=200)
