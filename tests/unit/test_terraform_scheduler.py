from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"

_JOBS = ("opportunity_scan", "campaign_run", "lead_sweep", "analytics_sync")


def test_scheduler_service_account_declared() -> None:
    body = (_TF / "scheduler.tf").read_text()
    assert 'resource "google_service_account" "scheduler"' in body


def test_all_four_batch_jobs_are_scheduled() -> None:
    body = (_TF / "scheduler.tf").read_text()
    for job in _JOBS:
        assert f"{job} = {{" in body


def test_scheduler_uses_its_own_service_account_not_the_app_one() -> None:
    # ADR-008 least privilege: the app's runtime SA (google_service_account.api)
    # runs the process itself -- it should not also be able to trigger jobs.
    body = (_TF / "scheduler.tf").read_text()
    assert "google_service_account.api" not in body
    assert body.count("google_service_account.scheduler.email") >= 2


def test_scheduler_invoker_role_scoped_per_job() -> None:
    body = (_TF / "scheduler.tf").read_text()
    block = body.split('resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker"', 1)[
        1
    ].split("\nresource ", 1)[0]
    assert 'role     = "roles/run.invoker"' in block
    assert "for_each = local.scheduled_jobs" in block


def test_campaign_run_scheduled_after_opportunity_scan() -> None:
    # campaign_run consumes opportunities the scan just produced -- it must
    # run strictly later in the same day, not before or concurrently.
    body = (_TF / "scheduler.tf").read_text()
    scan_schedule = (
        body.split("opportunity_scan = {", 1)[1].split('schedule = "', 1)[1].split('"', 1)[0]
    )
    campaign_schedule = (
        body.split("campaign_run = {", 1)[1].split('schedule = "', 1)[1].split('"', 1)[0]
    )

    def _minute_of_day(cron: str) -> int:
        minute, hour = cron.split()[0], cron.split()[1]
        return int(hour) * 60 + int(minute)

    assert _minute_of_day(campaign_schedule) > _minute_of_day(scan_schedule)


def test_cloud_scheduler_job_declared_per_batch_job() -> None:
    body = (_TF / "scheduler.tf").read_text()
    block = body.split('resource "google_cloud_scheduler_job" "this"', 1)[1]
    assert "for_each = local.scheduled_jobs" in block
    assert "oauth_token" in block
    assert "google_service_account.scheduler.email" in block


def test_cloudscheduler_api_enabled() -> None:
    body = (_TF / "apis.tf").read_text()
    assert "cloudscheduler.googleapis.com" in body
