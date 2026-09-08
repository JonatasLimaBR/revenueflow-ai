# Fix pós-merge (2026-09-08): o 1º apply real do langfuse_service.tf falhou
# — Prisma não conseguia alcançar o IP público da instância Cloud SQL
# (`P1001: Can't reach database server`). A suposição original estava
# errada: `ipv4_enabled = true` sem `authorized_networks` não abre a
# instância pra qualquer IP, é o oposto — o Cloud SQL bloqueia por padrão
# toda conexão externa até a rede de origem ser explicitamente autorizada.
# Abrir `authorized_networks` pra `0.0.0.0/0` resolveria, mas exporia a
# autenticação do banco à internet inteira — rejeitado (ADR-031). A
# correção correta, e a recomendada pelo GCP pra Cloud Run -> Cloud SQL: um
# Serverless VPC Access connector + IP PRIVADO na instância, nunca saindo
# da rede do projeto.
data "google_compute_network" "default" {
  name = "default"
}

# Private Service Access: reserva um range de IPs internos e faz o peering
# que permite ao Cloud SQL ter um IP privado nessa rede.
resource "google_compute_global_address" "private_service_access" {
  name          = "${var.service_name}-psa-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = data.google_compute_network.default.id

  depends_on = [google_project_service.this]
}

resource "google_service_networking_connection" "private_service_access" {
  network                 = data.google_compute_network.default.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access.name]

  depends_on = [google_project_service.this]
}

# Serverless VPC Access connector: a ponte que deixa o Cloud Run do
# Langfuse alcançar o IP privado do Cloud SQL. egress PRIVATE_RANGES_ONLY
# (cloud_run.tf/langfuse_service.tf) mantém todo o resto do tráfego (Vertex
# AI, Gemini, chamadas externas) saindo direto, sem passar pelo connector.
#
# Fix pós-merge (2026-09-08): "${var.service_name}-langfuse-vpc" tem 28
# caracteres -- o connector ID do GCP aceita no máximo 25
# (^[a-z][-a-z0-9]{0,23}[a-z0-9]$), então o apply falhou com 400. "lf" no
# lugar de "langfuse" cabe (22 caracteres com o var.service_name default).
resource "google_vpc_access_connector" "langfuse" {
  name          = "${var.service_name}-lf-vpc"
  region        = var.region
  network       = data.google_compute_network.default.name
  ip_cidr_range = "10.8.0.0/28"
  # The GCP API rejects "must specify either max_throughput or
  # max_instances" when both are left implicit -- low, fixed bounds are
  # plenty for one low-traffic Cloud Run service reaching one Cloud SQL IP.
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.this]
}
