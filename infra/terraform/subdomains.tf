# Custom subdomains for the MCP public server and the portal, routed through
# the landing page's existing global Load Balancer (ADR-068) via Serverless
# NEG backends — same IP, same cert (extended), no new LB/IP.
locals {
  mcp_subdomain    = var.landing_domain != "" ? "mcp.${var.landing_domain}" : ""
  portal_subdomain = var.landing_domain != "" ? "portal.${var.landing_domain}" : ""
}

resource "google_compute_region_network_endpoint_group" "mcp_readonly" {
  count = var.landing_domain != "" ? 1 : 0

  name                  = "${var.service_name}-mcp-readonly-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.mcp_readonly.name
  }
}

resource "google_compute_backend_service" "mcp_readonly" {
  count = var.landing_domain != "" ? 1 : 0

  name                  = "${var.service_name}-mcp-readonly-backend"
  load_balancing_scheme = "EXTERNAL"

  backend {
    group = google_compute_region_network_endpoint_group.mcp_readonly[0].id
  }
}

resource "google_compute_region_network_endpoint_group" "portal" {
  count = var.landing_domain != "" ? 1 : 0

  name                  = "${var.service_name}-portal-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.portal.name
  }
}

resource "google_compute_backend_service" "portal" {
  count = var.landing_domain != "" ? 1 : 0

  name                  = "${var.service_name}-portal-backend"
  load_balancing_scheme = "EXTERNAL"

  backend {
    group = google_compute_region_network_endpoint_group.portal[0].id
  }
}
