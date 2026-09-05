# Static landing-page hosting: a public GCS bucket behind a global HTTP(S)
# Load Balancer with Cloud CDN enabled. Custom domain + managed TLS cert added
# in ADR-068 (mastavista.com.br) — additive on top of ADR-060's HTTP-only
# setup, exactly as that ADR anticipated: nothing here was recreated.
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
  name = "${var.service_name}-landing-proxy"
  # Redirects to HTTPS once var.landing_domain is set (ADR-068); serves the
  # bucket directly over HTTP when it's empty (ADR-060's original behavior).
  url_map = var.landing_domain != "" ? google_compute_url_map.landing_redirect[0].id : google_compute_url_map.landing.id
}

resource "google_compute_global_forwarding_rule" "landing" {
  name                  = "${var.service_name}-landing-fr"
  ip_address            = google_compute_global_address.landing.address
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.landing.id
  load_balancing_scheme = "EXTERNAL"
}

# Custom domain + managed TLS (ADR-068). var.landing_domain empty (the
# default for any other clone of this config) skips all of this — the
# HTTP-only setup above stays exactly as ADR-060 left it. DNS itself is
# outside Terraform: point an A record for var.landing_domain at
# google_compute_global_address.landing.address (output landing_page_ip) —
# the managed cert stays PROVISIONING until that resolves.
resource "google_compute_managed_ssl_certificate" "landing" {
  count = var.landing_domain != "" ? 1 : 0

  name = "${var.service_name}-landing-cert"

  managed {
    domains = [var.landing_domain]
  }
}

resource "google_compute_target_https_proxy" "landing" {
  count = var.landing_domain != "" ? 1 : 0

  name             = "${var.service_name}-landing-https-proxy"
  url_map          = google_compute_url_map.landing.id
  ssl_certificates = [google_compute_managed_ssl_certificate.landing[0].id]
}

resource "google_compute_global_forwarding_rule" "landing_https" {
  count = var.landing_domain != "" ? 1 : 0

  name                  = "${var.service_name}-landing-https-fr"
  ip_address            = google_compute_global_address.landing.address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.landing[0].id
  load_balancing_scheme = "EXTERNAL"
}

# HTTP now redirects to HTTPS instead of serving the bucket directly — the
# existing target_http_proxy points at this redirect map, not at
# google_compute_url_map.landing, once a domain is configured.
resource "google_compute_url_map" "landing_redirect" {
  count = var.landing_domain != "" ? 1 : 0

  name = "${var.service_name}-landing-redirect-map"

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}
