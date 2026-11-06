from apscheduler.schedulers.background import BackgroundScheduler
from app.jobs.drain_job        import run_drain_job
from app.jobs.hotspot_job      import run_hotspot_job
from app.jobs.civicpulse_job   import run_civicpulse_job
from app.jobs.coordination_job import run_coordination_job
from app.jobs.trust_job        import run_trust_job

# 1.6 job modules
from app.jobs.sla_breach_job import run_sla_breach_job
from app.jobs.notification_job import run_notification_flush_job
from app.jobs.decay_job import run_decay_job

def start_scheduler(db):
    s = BackgroundScheduler(daemon=True, timezone="UTC")
    
    # 1.5 cron/interval jobs
    s.add_job(lambda: run_drain_job(db),        "interval", hours=6,    id="drain")
    s.add_job(lambda: run_hotspot_job(db),      "interval", hours=12,   id="hotspots")
    s.add_job(lambda: run_civicpulse_job(db),   "interval", hours=24,   id="civicpulse")
    s.add_job(lambda: run_coordination_job(db), "cron", day_of_week="mon", hour=2, id="coord")
    s.add_job(lambda: run_trust_job(db),        "cron", day_of_week="mon", hour=3, id="trust")
    
    # 1.6 background audit / processing tasks
    s.add_job(lambda: run_sla_breach_job(db),   "interval", hours=1,    id="sla")
    s.add_job(lambda: run_notification_flush_job(db), "interval", seconds=60, id="notifications")
    s.add_job(lambda: run_decay_job(db),        "cron", day=1, hour=0, minute=0, id="decay")
    
    s.start()
    return s
