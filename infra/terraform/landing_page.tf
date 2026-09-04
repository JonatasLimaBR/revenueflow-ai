# Static landing-page hosting: a public GCS bucket behind a global HTTP Load
# Balancer with Cloud CDN enabled, so the site gets edge caching and a stable
# static IP today. No custom domain yet (ADR-060) — HTTPS is deliberately out
# of scope until one exists; adding it later is additive (a managed cert + an
# HTTPS proxy pointed at the same backend), nothing here needs to be recreated.
resource "google_storage_bucket" "landing" {
  name                        = "${var.project_id}-landing"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"
  }

  depends_on = [google_project_service.this]
}

resource "google_storage_bucket_iam_member" "landing_public_read" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_compute_backend_bucket" "landing" {
  name        = "${var.service_name}-landing-backend"
  bucket_name = google_storage_bucket.landing.name
  enable_cdn  = true
}

resource "google_compute_global_address" "landing" {
  name = "${var.service_name}-landing-ip"
}

resource "google_compute_url_map" "landing" {
  name            = "${var.service_name}-landing-map"
  default_service = google_compute_backend_bucket.landing.id
}

resource "google_compute_target_http_proxy" "landing" {
  name    = "${var.service_name}-landing-proxy"
  url_map = google_compute_url_map.landing.id
}

resource "google_compute_global_forwarding_rule" "landing" {
  name                  = "${var.service_name}-landing-fr"
  ip_address            = google_compute_global_address.landing.address
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.landing.id
  load_balancing_scheme = "EXTERNAL"
}
