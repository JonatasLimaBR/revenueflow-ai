# Cloud Monitoring dashboards + alerts for SPEC-034 (ADR-056).
# AI metrics come from the structured "audit.turn" log line emitted once per
# turn by AuditTracer.flush(); request metrics are native Cloud Run metrics.
# Everything here only adds resources.

locals {
  turn_filter    = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=\"audit.turn\""
  alert_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}

resource "google_logging_metric" "turn_cost_usd" {
  name        = "revenueflow_turn_cost_usd"
  description = "Per-turn AI cost in USD (audit.turn)"
  filter      = local.turn_filter

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }

  value_extractor = "EXTRACT(jsonPayload.cost_usd)"

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 32
      growth_factor      = 2
      scale              = 0.0001
    }
  }

  depends_on = [google_project_service.this]
}

# Plain-numeric sibling of turn_cost_usd, for the ai_cost_per_hour alert only
# (found live in production, ADR-071): Cloud Monitoring's ALIGN_SUM does not
# reduce a DISTRIBUTION metric to a scalar (only percentile aligners do,
# which would change the alert from "total $/hour" to "one turn's
# percentile") — a second, non-distribution metric is the correct fix, not a
# different aligner on the histogram metric the dashboard already depends on.
resource "google_logging_metric" "turn_cost_usd_total" {
  name        = "revenueflow_turn_cost_usd_total"
  description = "Per-turn AI cost in USD, plain numeric for ALIGN_SUM alerting (audit.turn)"
  filter      = local.turn_filter

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DOUBLE"
    unit        = "1"
  }

  value_extractor = "EXTRACT(jsonPayload.cost_usd)"

  depends_on = [google_project_service.this]
}

resource "google_logging_metric" "turn_latency_ms" {
  name        = "revenueflow_turn_latency_ms"
  description = "Per-turn latency in ms (audit.turn)"
  filter      = local.turn_filter

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "ms"
  }

  value_extractor = "EXTRACT(jsonPayload.latency_ms)"

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 32
      growth_factor      = 2
      scale              = 1
    }
  }

  depends_on = [google_project_service.this]
}

resource "google_logging_metric" "turns" {
  name        = "revenueflow_turns"
  description = "Audited turns, labelled by outcome (audit.turn)"
  filter      = local.turn_filter

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"

    labels {
      key         = "outcome"
      value_type  = "STRING"
      description = "Turn outcome from tracer.end()"
    }
  }

  label_extractors = {
    "outcome" = "EXTRACT(jsonPayload.outcome)"
  }

  depends_on = [google_project_service.this]
}

resource "google_logging_metric" "handoffs" {
  name        = "revenueflow_handoffs"
  description = "Turns that ended in a human handoff (audit.turn)"
  filter      = "${local.turn_filter} AND jsonPayload.handoff=\"true\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  depends_on = [google_project_service.this]
}

resource "google_logging_metric" "tool_failures" {
  name        = "revenueflow_tool_failures"
  description = "Unhandled tool exceptions per turn (audit.turn)"
  filter      = local.turn_filter

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }

  value_extractor = "EXTRACT(jsonPayload.tool_failures)"

  bucket_options {
    linear_buckets {
      num_finite_buckets = 10
      width              = 1
      offset             = 0
    }
  }

  depends_on = [google_project_service.this]
}

# Plain-numeric sibling of tool_failures, same reason as turn_cost_usd_total
# above (ADR-071) — the tool_failures alert needs ALIGN_SUM to work.
resource "google_logging_metric" "tool_failures_total" {
  name        = "revenueflow_tool_failures_total"
  description = "Unhandled tool exceptions per turn, plain numeric for ALIGN_SUM alerting (audit.turn)"
  filter      = local.turn_filter

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  value_extractor = "EXTRACT(jsonPayload.tool_failures)"

  depends_on = [google_project_service.this]
}

resource "google_monitoring_notification_channel" "email" {
  count = var.alert_email != "" ? 1 : 0

  display_name = "RevenueFlow alerts"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.this]
}

resource "google_monitoring_dashboard" "revenueflow_ops" {
  dashboard_json = file("${path.module}/dashboards/revenueflow_ops.json")

  depends_on = [google_project_service.this]
}

# Read-only dashboard access for teammates without a full project role
# (ADR-065). Cloud Monitoring has no per-dashboard IAM — roles/monitoring.viewer
# at the project level is the narrowest predefined role available; it grants
# read access to dashboards/metrics/alerting policies only, nothing else in
# the project. Empty by default (var.dashboard_viewer_emails) until the user
# provides real emails to onboard.
resource "google_project_iam_member" "dashboard_viewer" {
  for_each = toset(var.dashboard_viewer_emails)

  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "user:${each.value}"
}

resource "google_monitoring_alert_policy" "request_5xx_ratio" {
  display_name = "RevenueFlow 5xx ratio high"
  combiner     = "OR"

  conditions {
    display_name = "5xx / total requests over ${var.alert_5xx_ratio}"

    condition_threshold {
      filter             = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND metric.label.response_code_class=\"5xx\""
      denominator_filter = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\""

      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_5xx_ratio
      duration        = "300s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }

      denominator_aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = local.alert_channels

  documentation {
    content   = "5xx rate above ${var.alert_5xx_ratio}. Check the latest revision logs and the Cloud SQL / Pub/Sub dependencies."
    mime_type = "text/markdown"
  }

  depends_on = [google_project_service.this]
}

resource "google_monitoring_alert_policy" "request_latency_p95" {
  display_name = "RevenueFlow request latency p95 high"
  combiner     = "OR"

  conditions {
    display_name = "p95 request latency over ${var.alert_p95_latency_ms} ms"

    condition_threshold {
      filter = "metric.type=\"run.googleapis.com/request_latencies\" AND resource.type=\"cloud_run_revision\""

      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_p95_latency_ms
      duration        = "600s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }

  notification_channels = local.alert_channels

  documentation {
    content   = "Request p95 above ${var.alert_p95_latency_ms} ms for 10 min. Check the turn-latency tile and Cloud Trace for slow spans."
    mime_type = "text/markdown"
  }

  depends_on = [google_project_service.this]
}

resource "google_monitoring_alert_policy" "tool_failures" {
  display_name = "RevenueFlow tool exceptions high"
  combiner     = "OR"

  conditions {
    display_name = "tool exceptions over ${var.alert_tool_failures_per_hour} / hour"

    condition_threshold {
      filter = "metric.type=\"logging.googleapis.com/user/revenueflow_tool_failures_total\" AND resource.type=\"cloud_run_revision\""

      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_tool_failures_per_hour
      duration        = "0s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = local.alert_channels

  documentation {
    content   = "More than ${var.alert_tool_failures_per_hour} unhandled tool exceptions in an hour. Inspect audit_event.events for the failing tool spans."
    mime_type = "text/markdown"
  }

  # Explicit — the filter above references the metric by name (a string),
  # not by resource attribute, so Terraform has no implicit dependency edge.
  depends_on = [google_project_service.this, google_logging_metric.tool_failures_total]
}

resource "google_monitoring_alert_policy" "ai_cost_per_hour" {
  display_name = "RevenueFlow AI cost per hour high"
  combiner     = "OR"

  conditions {
    display_name = "AI cost over $${var.alert_ai_cost_per_hour_usd} / hour"

    condition_threshold {
      filter = "metric.type=\"logging.googleapis.com/user/revenueflow_turn_cost_usd_total\" AND resource.type=\"cloud_run_revision\""

      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_ai_cost_per_hour_usd
      duration        = "0s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = local.alert_channels

  documentation {
    content   = "AI spend above $${var.alert_ai_cost_per_hour_usd}/hour. Check v_ai_cost_per_conversation and MODEL_PRICES."
    mime_type = "text/markdown"
  }

  # Explicit — same reason as tool_failures above.
  depends_on = [google_project_service.this, google_logging_metric.turn_cost_usd_total]
}

resource "google_monitoring_alert_policy" "no_turns" {
  display_name = "RevenueFlow no audited turns"
  combiner     = "OR"

  conditions {
    display_name = "no audited turn for ${var.alert_no_turns_minutes} min"

    condition_absent {
      filter   = "metric.type=\"logging.googleapis.com/user/revenueflow_turns\" AND resource.type=\"cloud_run_revision\""
      duration = "${var.alert_no_turns_minutes * 60}s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = local.alert_channels

  documentation {
    content   = "No audit.turn log line for ${var.alert_no_turns_minutes} min. The consumer may be down; check the revision and the Pub/Sub subscription backlog."
    mime_type = "text/markdown"
  }

  depends_on = [google_project_service.this]
}
