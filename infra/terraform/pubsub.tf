# Names match the application contract exactly: services/ingest.py publishes to
# topic "revenueflow.messages" and worker/subscriber.py pulls the subscription
# "revenueflow.messages". Dots are legal in Pub/Sub ids.

resource "google_pubsub_topic" "messages" {
  name       = "revenueflow.messages"
  depends_on = [google_project_service.this]
}

resource "google_pubsub_topic" "messages_dlq" {
  name       = "revenueflow.messages.dlq"
  depends_on = [google_project_service.this]
}

resource "google_pubsub_subscription" "messages" {
  name  = "revenueflow.messages"
  topic = google_pubsub_topic.messages.id

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.messages_dlq.id
    max_delivery_attempts = 5
  }
}

# The runtime SA publishes and consumes; grants scoped to the resources.
resource "google_pubsub_topic_iam_member" "api_publisher" {
  topic  = google_pubsub_topic.messages.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_pubsub_subscription_iam_member" "api_subscriber" {
  subscription = google_pubsub_subscription.messages.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.api.email}"
}

# The Pub/Sub service agent needs to publish to the DLQ and consume from the
# main subscription for dead-lettering to work.
locals {
  pubsub_agent = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.messages_dlq.id
  role   = "roles/pubsub.publisher"
  member = local.pubsub_agent
}

resource "google_pubsub_subscription_iam_member" "dlq_subscriber" {
  subscription = google_pubsub_subscription.messages.id
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}
