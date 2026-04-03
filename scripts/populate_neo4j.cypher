// ============================================================================
// OpenSRE Knowledge Graph — otel-demo Cluster Topology
// Populates Neo4j with K8s infrastructure and service dependencies
// ============================================================================

// --- Clear existing data ---
MATCH (n) DETACH DELETE n;

// ============================================================================
// 1. CLUSTER & NAMESPACE
// ============================================================================

CREATE (cluster:KubernetesCluster {name: 'opensre-test', provider: 'kind', version: 'v1.35.0'})
CREATE (ns:KubernetesNamespace {name: 'otel-demo'})
CREATE (cluster)-[:HAS_NAMESPACE]->(ns);

// ============================================================================
// 2. DEPLOYMENTS (stable names — no pod hashes)
// ============================================================================

// --- Application Services ---
CREATE (d_cart:KubernetesDeployment {name: 'otel-demo-cartservice', replicas: 1, image: 'demo:1.11.1-cartservice', language: 'dotnet', port: 8080})
CREATE (d_checkout:KubernetesDeployment {name: 'otel-demo-checkoutservice', replicas: 1, image: 'demo:1.11.1-checkoutservice', language: 'go', port: 8080})
CREATE (d_currency:KubernetesDeployment {name: 'otel-demo-currencyservice', replicas: 1, image: 'demo:1.11.1-currencyservice', language: 'cpp', port: 8080})
CREATE (d_email:KubernetesDeployment {name: 'otel-demo-emailservice', replicas: 1, image: 'demo:1.11.1-emailservice', language: 'ruby', port: 8080})
CREATE (d_frontend:KubernetesDeployment {name: 'otel-demo-frontend', replicas: 1, image: 'demo:1.11.1-frontend', language: 'typescript', port: 8080})
CREATE (d_payment:KubernetesDeployment {name: 'otel-demo-paymentservice', replicas: 1, image: 'demo:1.11.1-paymentservice', language: 'javascript', port: 8080})
CREATE (d_productcatalog:KubernetesDeployment {name: 'otel-demo-productcatalogservice', replicas: 1, image: 'demo:1.11.1-productcatalogservice', language: 'go', port: 8080})
CREATE (d_recommendation:KubernetesDeployment {name: 'otel-demo-recommendationservice', replicas: 1, image: 'demo:1.11.1-recommendationservice', language: 'python', port: 8080})
CREATE (d_shipping:KubernetesDeployment {name: 'otel-demo-shippingservice', replicas: 1, image: 'demo:1.11.1-shippingservice', language: 'rust', port: 8080})
CREATE (d_ad:KubernetesDeployment {name: 'otel-demo-adservice', replicas: 1, image: 'demo:1.11.1-adservice', language: 'java', port: 8080})
CREATE (d_quote:KubernetesDeployment {name: 'otel-demo-quoteservice', replicas: 1, image: 'demo:1.11.1-quoteservice', language: 'php', port: 8080})
CREATE (d_imageprovider:KubernetesDeployment {name: 'otel-demo-imageprovider', replicas: 1, image: 'demo:1.11.1-imageprovider', language: 'go', port: 8081})
CREATE (d_accounting:KubernetesDeployment {name: 'otel-demo-accountingservice', replicas: 1, image: 'demo:1.11.1-accountingservice', language: 'go', port: 0})
CREATE (d_fraud:KubernetesDeployment {name: 'otel-demo-frauddetectionservice', replicas: 1, image: 'demo:1.11.1-frauddetectionservice', language: 'kotlin', port: 0})

// --- Infrastructure Services ---
CREATE (d_frontendproxy:KubernetesDeployment {name: 'otel-demo-frontendproxy', replicas: 1, image: 'demo:1.11.1-frontendproxy', language: 'go', port: 8080})
CREATE (d_loadgen:KubernetesDeployment {name: 'otel-demo-loadgenerator', replicas: 1, image: 'demo:1.11.1-loadgenerator', language: 'python', port: 8089})
CREATE (d_kafka:KubernetesDeployment {name: 'otel-demo-kafka', replicas: 1, image: 'demo:1.11.1-kafka', language: 'java', port: 9092})
CREATE (d_valkey:KubernetesDeployment {name: 'otel-demo-valkey', replicas: 1, image: 'valkey:7.2-alpine', language: 'c', port: 6379})

// --- Observability Stack ---
CREATE (d_otelcol:KubernetesDeployment {name: 'otel-demo-otelcol', replicas: 1, image: 'opentelemetry-collector-contrib:0.108.0', language: 'go', port: 4317})
CREATE (d_jaeger:KubernetesDeployment {name: 'otel-demo-jaeger', replicas: 1, image: 'all-in-one:1.53.0', language: 'go', port: 16686})
CREATE (d_prometheus:KubernetesDeployment {name: 'otel-demo-prometheus-server', replicas: 1, image: 'prometheus:v2.53.1', language: 'go', port: 9090})
CREATE (d_grafana:KubernetesDeployment {name: 'otel-demo-grafana', replicas: 1, image: 'grafana:11.1.0', language: 'go', port: 3000})
CREATE (s_opensearch:KubernetesStatefulSet {name: 'otel-demo-opensearch', replicas: 1, image: 'opensearch', language: 'java', port: 9200});

// ============================================================================
// 3. SERVICES (K8s Service objects)
// ============================================================================

CREATE (svc_cart:KubernetesService {name: 'otel-demo-cartservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_checkout:KubernetesService {name: 'otel-demo-checkoutservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_currency:KubernetesService {name: 'otel-demo-currencyservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_email:KubernetesService {name: 'otel-demo-emailservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_frontend:KubernetesService {name: 'otel-demo-frontend', type: 'NodePort', port: 8080, nodePort: 30080, protocol: 'HTTP'})
CREATE (svc_payment:KubernetesService {name: 'otel-demo-paymentservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_productcatalog:KubernetesService {name: 'otel-demo-productcatalogservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_recommendation:KubernetesService {name: 'otel-demo-recommendationservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_shipping:KubernetesService {name: 'otel-demo-shippingservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_ad:KubernetesService {name: 'otel-demo-adservice', type: 'ClusterIP', port: 8080, protocol: 'gRPC'})
CREATE (svc_quote:KubernetesService {name: 'otel-demo-quoteservice', type: 'ClusterIP', port: 8080, protocol: 'HTTP'})
CREATE (svc_imageprovider:KubernetesService {name: 'otel-demo-imageprovider', type: 'ClusterIP', port: 8081, protocol: 'HTTP'})
CREATE (svc_frontendproxy:KubernetesService {name: 'otel-demo-frontendproxy', type: 'ClusterIP', port: 8080, protocol: 'HTTP'})
CREATE (svc_loadgen:KubernetesService {name: 'otel-demo-loadgenerator', type: 'ClusterIP', port: 8089, protocol: 'HTTP'})
CREATE (svc_kafka:KubernetesService {name: 'otel-demo-kafka', type: 'ClusterIP', port: 9092, protocol: 'TCP'})
CREATE (svc_valkey:KubernetesService {name: 'otel-demo-valkey', type: 'ClusterIP', port: 6379, protocol: 'TCP'})
CREATE (svc_otelcol:KubernetesService {name: 'otel-demo-otelcol', type: 'ClusterIP', port: 4317, protocol: 'gRPC'})
CREATE (svc_jaeger_query:KubernetesService {name: 'otel-demo-jaeger-query', type: 'ClusterIP', port: 16686, protocol: 'HTTP'})
CREATE (svc_jaeger_collector:KubernetesService {name: 'otel-demo-jaeger-collector', type: 'ClusterIP', port: 4317, protocol: 'gRPC'})
CREATE (svc_prometheus:KubernetesService {name: 'otel-demo-prometheus-server', type: 'NodePort', port: 9090, nodePort: 30090, protocol: 'HTTP'})
CREATE (svc_grafana:KubernetesService {name: 'otel-demo-grafana', type: 'NodePort', port: 80, nodePort: 30030, protocol: 'HTTP'})
CREATE (svc_opensearch:KubernetesService {name: 'otel-demo-opensearch', type: 'NodePort', port: 9200, nodePort: 30920, protocol: 'HTTP'});

// ============================================================================
// 4. CONFIGMAPS
// ============================================================================

CREATE (cm_otelcol:KubernetesConfigMap {name: 'otel-demo-otelcol', description: 'OpenTelemetry Collector pipeline configuration'})
CREATE (cm_grafana:KubernetesConfigMap {name: 'otel-demo-grafana', description: 'Grafana main configuration'})
CREATE (cm_grafana_dash:KubernetesConfigMap {name: 'otel-demo-grafana-dashboards', description: 'Grafana dashboard JSON definitions'})
CREATE (cm_prometheus:KubernetesConfigMap {name: 'otel-demo-prometheus-server', description: 'Prometheus scrape configuration'})
CREATE (cm_opensearch:KubernetesConfigMap {name: 'otel-demo-opensearch-config', description: 'OpenSearch cluster configuration'});

// ============================================================================
// 5. NAMESPACE -> RESOURCE RELATIONSHIPS
// ============================================================================

// Namespace owns all deployments
MATCH (ns:KubernetesNamespace {name: 'otel-demo'}), (d:KubernetesDeployment)
WHERE d.name STARTS WITH 'otel-demo-'
CREATE (ns)-[:HAS_DEPLOYMENT]->(d);

// Namespace owns statefulsets
MATCH (ns:KubernetesNamespace {name: 'otel-demo'}), (ss:KubernetesStatefulSet)
WHERE ss.name STARTS WITH 'otel-demo-'
CREATE (ns)-[:HAS_STATEFULSET]->(ss);

// Namespace owns all services
MATCH (ns:KubernetesNamespace {name: 'otel-demo'}), (s:KubernetesService)
WHERE s.name STARTS WITH 'otel-demo-'
CREATE (ns)-[:HAS_SERVICE]->(s);

// Namespace owns all configmaps
MATCH (ns:KubernetesNamespace {name: 'otel-demo'}), (cm:KubernetesConfigMap)
WHERE cm.name STARTS WITH 'otel-demo-'
CREATE (ns)-[:HAS_CONFIGMAP]->(cm);

// ============================================================================
// 6. SERVICE -> DEPLOYMENT (service selects deployment's pods)
// ============================================================================

MATCH (s:KubernetesService {name: 'otel-demo-cartservice'}), (d:KubernetesDeployment {name: 'otel-demo-cartservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-checkoutservice'}), (d:KubernetesDeployment {name: 'otel-demo-checkoutservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-currencyservice'}), (d:KubernetesDeployment {name: 'otel-demo-currencyservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-emailservice'}), (d:KubernetesDeployment {name: 'otel-demo-emailservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-frontend'}), (d:KubernetesDeployment {name: 'otel-demo-frontend'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-paymentservice'}), (d:KubernetesDeployment {name: 'otel-demo-paymentservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-productcatalogservice'}), (d:KubernetesDeployment {name: 'otel-demo-productcatalogservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-recommendationservice'}), (d:KubernetesDeployment {name: 'otel-demo-recommendationservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-shippingservice'}), (d:KubernetesDeployment {name: 'otel-demo-shippingservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-adservice'}), (d:KubernetesDeployment {name: 'otel-demo-adservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-quoteservice'}), (d:KubernetesDeployment {name: 'otel-demo-quoteservice'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-imageprovider'}), (d:KubernetesDeployment {name: 'otel-demo-imageprovider'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-frontendproxy'}), (d:KubernetesDeployment {name: 'otel-demo-frontendproxy'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-loadgenerator'}), (d:KubernetesDeployment {name: 'otel-demo-loadgenerator'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-kafka'}), (d:KubernetesDeployment {name: 'otel-demo-kafka'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-valkey'}), (d:KubernetesDeployment {name: 'otel-demo-valkey'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-otelcol'}), (d:KubernetesDeployment {name: 'otel-demo-otelcol'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-jaeger-query'}), (d:KubernetesDeployment {name: 'otel-demo-jaeger'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-jaeger-collector'}), (d:KubernetesDeployment {name: 'otel-demo-jaeger'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-prometheus-server'}), (d:KubernetesDeployment {name: 'otel-demo-prometheus-server'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-grafana'}), (d:KubernetesDeployment {name: 'otel-demo-grafana'}) CREATE (s)-[:ROUTES_TO]->(d);
MATCH (s:KubernetesService {name: 'otel-demo-opensearch'}), (ss:KubernetesStatefulSet {name: 'otel-demo-opensearch'}) CREATE (s)-[:ROUTES_TO]->(ss);

// ============================================================================
// 7. CONFIGMAP -> DEPLOYMENT (configmap consumed by deployment)
// ============================================================================

MATCH (cm:KubernetesConfigMap {name: 'otel-demo-otelcol'}), (d:KubernetesDeployment {name: 'otel-demo-otelcol'}) CREATE (d)-[:USES_CONFIGMAP]->(cm);
MATCH (cm:KubernetesConfigMap {name: 'otel-demo-grafana'}), (d:KubernetesDeployment {name: 'otel-demo-grafana'}) CREATE (d)-[:USES_CONFIGMAP]->(cm);
MATCH (cm:KubernetesConfigMap {name: 'otel-demo-grafana-dashboards'}), (d:KubernetesDeployment {name: 'otel-demo-grafana'}) CREATE (d)-[:USES_CONFIGMAP]->(cm);
MATCH (cm:KubernetesConfigMap {name: 'otel-demo-prometheus-server'}), (d:KubernetesDeployment {name: 'otel-demo-prometheus-server'}) CREATE (d)-[:USES_CONFIGMAP]->(cm);
MATCH (cm:KubernetesConfigMap {name: 'otel-demo-opensearch-config'}), (ss:KubernetesStatefulSet {name: 'otel-demo-opensearch'}) CREATE (ss)-[:USES_CONFIGMAP]->(cm);

// ============================================================================
// 8. SERVICE DEPENDENCIES (extracted from env vars — the core value)
//    DEPENDS_ON means: source calls target at runtime
// ============================================================================

// --- frontend (entry point) depends on 7 backend services ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontend'}), (tgt:KubernetesDeployment {name: 'otel-demo-adservice'}) CREATE (src)-[:DEPENDS_ON {via: 'AD_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontend'}), (tgt:KubernetesDeployment {name: 'otel-demo-cartservice'}) CREATE (src)-[:DEPENDS_ON {via: 'CART_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontend'}), (tgt:KubernetesDeployment {name: 'otel-demo-checkoutservice'}) CREATE (src)-[:DEPENDS_ON {via: 'CHECKOUT_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontend'}), (tgt:KubernetesDeployment {name: 'otel-demo-currencyservice'}) CREATE (src)-[:DEPENDS_ON {via: 'CURRENCY_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontend'}), (tgt:KubernetesDeployment {name: 'otel-demo-productcatalogservice'}) CREATE (src)-[:DEPENDS_ON {via: 'PRODUCT_CATALOG_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontend'}), (tgt:KubernetesDeployment {name: 'otel-demo-recommendationservice'}) CREATE (src)-[:DEPENDS_ON {via: 'RECOMMENDATION_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontend'}), (tgt:KubernetesDeployment {name: 'otel-demo-shippingservice'}) CREATE (src)-[:DEPENDS_ON {via: 'SHIPPING_SERVICE_ADDR', port: 8080}]->(tgt);

// --- checkoutservice (critical checkout path) depends on 6 services + kafka ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-checkoutservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-cartservice'}) CREATE (src)-[:DEPENDS_ON {via: 'CART_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-checkoutservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-currencyservice'}) CREATE (src)-[:DEPENDS_ON {via: 'CURRENCY_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-checkoutservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-emailservice'}) CREATE (src)-[:DEPENDS_ON {via: 'EMAIL_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-checkoutservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-paymentservice'}) CREATE (src)-[:DEPENDS_ON {via: 'PAYMENT_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-checkoutservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-productcatalogservice'}) CREATE (src)-[:DEPENDS_ON {via: 'PRODUCT_CATALOG_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-checkoutservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-shippingservice'}) CREATE (src)-[:DEPENDS_ON {via: 'SHIPPING_SERVICE_ADDR', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-checkoutservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-kafka'}) CREATE (src)-[:DEPENDS_ON {via: 'KAFKA_SERVICE_ADDR', port: 9092}]->(tgt);

// --- cartservice depends on valkey (cache) ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-cartservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-valkey'}) CREATE (src)-[:DEPENDS_ON {via: 'VALKEY_ADDR', port: 6379}]->(tgt);

// --- recommendationservice depends on productcatalog ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-recommendationservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-productcatalogservice'}) CREATE (src)-[:DEPENDS_ON {via: 'PRODUCT_CATALOG_SERVICE_ADDR', port: 8080}]->(tgt);

// --- shippingservice depends on quoteservice ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-shippingservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-quoteservice'}) CREATE (src)-[:DEPENDS_ON {via: 'QUOTE_SERVICE_ADDR', port: 8080}]->(tgt);

// --- frontendproxy routes to frontend, grafana, jaeger, imageprovider, loadgenerator ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontendproxy'}), (tgt:KubernetesDeployment {name: 'otel-demo-frontend'}) CREATE (src)-[:DEPENDS_ON {via: 'FRONTEND_HOST', port: 8080}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontendproxy'}), (tgt:KubernetesDeployment {name: 'otel-demo-grafana'}) CREATE (src)-[:DEPENDS_ON {via: 'GRAFANA_SERVICE_HOST', port: 3000}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontendproxy'}), (tgt:KubernetesDeployment {name: 'otel-demo-jaeger'}) CREATE (src)-[:DEPENDS_ON {via: 'JAEGER_SERVICE_HOST', port: 16686}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontendproxy'}), (tgt:KubernetesDeployment {name: 'otel-demo-imageprovider'}) CREATE (src)-[:DEPENDS_ON {via: 'IMAGE_PROVIDER_HOST', port: 8081}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frontendproxy'}), (tgt:KubernetesDeployment {name: 'otel-demo-loadgenerator'}) CREATE (src)-[:DEPENDS_ON {via: 'LOCUST_WEB_HOST', port: 8089}]->(tgt);

// --- loadgenerator drives traffic through frontendproxy ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-loadgenerator'}), (tgt:KubernetesDeployment {name: 'otel-demo-frontendproxy'}) CREATE (src)-[:DEPENDS_ON {via: 'LOCUST_HOST', port: 8080}]->(tgt);

// --- kafka consumers: accountingservice and frauddetectionservice ---
MATCH (src:KubernetesDeployment {name: 'otel-demo-accountingservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-kafka'}) CREATE (src)-[:DEPENDS_ON {via: 'KAFKA_SERVICE_ADDR', port: 9092}]->(tgt);
MATCH (src:KubernetesDeployment {name: 'otel-demo-frauddetectionservice'}), (tgt:KubernetesDeployment {name: 'otel-demo-kafka'}) CREATE (src)-[:DEPENDS_ON {via: 'KAFKA_SERVICE_ADDR', port: 9092}]->(tgt);

// --- All services send telemetry to otelcol ---
MATCH (d:KubernetesDeployment), (otelcol:KubernetesDeployment {name: 'otel-demo-otelcol'})
WHERE d.name STARTS WITH 'otel-demo-'
  AND d.name <> 'otel-demo-otelcol'
  AND d.name <> 'otel-demo-grafana'
  AND d.name <> 'otel-demo-prometheus-server'
  AND d.name <> 'otel-demo-jaeger'
CREATE (d)-[:SENDS_TELEMETRY_TO {protocol: 'OTLP', port: 4317}]->(otelcol);

// --- otelcol exports to jaeger, prometheus, opensearch ---
MATCH (otelcol:KubernetesDeployment {name: 'otel-demo-otelcol'}), (jaeger:KubernetesDeployment {name: 'otel-demo-jaeger'}) CREATE (otelcol)-[:EXPORTS_TO {data: 'traces', protocol: 'OTLP'}]->(jaeger);
MATCH (otelcol:KubernetesDeployment {name: 'otel-demo-otelcol'}), (prom:KubernetesDeployment {name: 'otel-demo-prometheus-server'}) CREATE (otelcol)-[:EXPORTS_TO {data: 'metrics', protocol: 'prometheus'}]->(prom);
MATCH (otelcol:KubernetesDeployment {name: 'otel-demo-otelcol'}), (os:KubernetesStatefulSet {name: 'otel-demo-opensearch'}) CREATE (otelcol)-[:EXPORTS_TO {data: 'logs', protocol: 'HTTP'}]->(os);

// --- grafana reads from prometheus ---
MATCH (grafana:KubernetesDeployment {name: 'otel-demo-grafana'}), (prom:KubernetesDeployment {name: 'otel-demo-prometheus-server'}) CREATE (grafana)-[:READS_FROM {data: 'metrics'}]->(prom);

// ============================================================================
// 9. INDEXES for query performance
// ============================================================================

CREATE INDEX IF NOT EXISTS FOR (d:KubernetesDeployment) ON (d.name);
CREATE INDEX IF NOT EXISTS FOR (s:KubernetesService) ON (s.name);
CREATE INDEX IF NOT EXISTS FOR (ns:KubernetesNamespace) ON (ns.name);
CREATE INDEX IF NOT EXISTS FOR (c:KubernetesCluster) ON (c.name);
CREATE INDEX IF NOT EXISTS FOR (cm:KubernetesConfigMap) ON (cm.name);
CREATE INDEX IF NOT EXISTS FOR (ss:KubernetesStatefulSet) ON (ss.name);
