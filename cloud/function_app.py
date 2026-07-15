"""Sigma-bet scanner — Azure Functions (Python v2 model).

Timers (UTC; ET = UTC-4 in summer):
  scan_cycle : every 2h during market hours (13:45, 15:45, 17:45, 19:45 UTC Mon-Fri
               = 9:45a, 11:45a, 1:45p, 3:45p ET)
  eod_update : 09:00 UTC Tue-Sat (5:00a ET) — flat files publish overnight

HTTP:
  GET /api/run?job=scan|eod  (function key) — manual kick for testing
"""
import logging
import azure.functions as func
from scanner import core

app = func.FunctionApp()

@app.timer_trigger(schedule="0 45 13,15,17,19 * * 1-5", arg_name="timer", run_on_startup=False)
def scan_cycle(timer: func.TimerRequest) -> None:
    result = core.run_scan()
    logging.info("scan_cycle: %s", result)

# EOD build + morning digest at ~4:30a ET, after the OPRA flat file publishes
# (observed 11:45p-3:30a ET; 4:30 clears it with self-healing retries for late
# files). Fires at BOTH DST-candidate UTC times (08:30=EDT, 09:30=EST); run_eod
# is idempotent and it sends the consolidated morning digest via send_brief's
# Central-hour gate so exactly one email lands at ~4:30a ET (3:30a CT) year-round.
@app.timer_trigger(schedule="0 30 8,9 * * 2-6", arg_name="timer", run_on_startup=False)
def eod_update(timer: func.TimerRequest) -> None:
    result = core.run_eod()
    logging.info("eod_update: %s", result)

# Afternoon digest — pre-close (2:30p CT). Fires at BOTH DST-candidate UTC times;
# send_brief gates on real Central time. The morning digest is folded into
# eod_update above (one consolidated email: ETF reversion + microcap flow).
@app.timer_trigger(schedule="0 30 19,20 * * 1-5", arg_name="timer", run_on_startup=False)
def brief_preclose(timer: func.TimerRequest) -> None:   # 19:30 UTC=CDT, 20:30 UTC=CST -> 2:30p CT
    logging.info("brief_preclose: %s", core.send_brief("pm"))

@app.route(route="run", auth_level=func.AuthLevel.FUNCTION)
def run_manual(req: func.HttpRequest) -> func.HttpResponse:
    job = req.params.get("job", "scan")
    if job == "eod":
        result = core.run_eod()
    elif job == "brief":
        result = core.send_brief(req.params.get("tag", "pm"), force=True)
    else:
        result = core.run_scan()
    return func.HttpResponse(result, status_code=200)
