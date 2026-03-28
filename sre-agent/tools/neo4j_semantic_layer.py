"""
Neo4j Semantic Layer for AI-Engine.

This module provides a semantic layer on top of Neo4j for querying
Kubernetes infrastructure data. It leverages LangChain's Neo4j integration
to provide structured tools for interacting with the graph database.
"""

import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

# Get Neo4j connection parameters from environment variables
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

logger = logging.getLogger(__name__)


class KubernetesGraphTools:
    """Semantic layer providing tools for Kubernetes infrastructure graph interactions."""

    def __init__(self):
        """Initialize the Neo4j connection."""
        self.driver = None
        self.openai_client = None

        try:
            # Initialize OpenAI client for Cypher generation if possible
            try:
                from openai import OpenAI

                self.openai_client = OpenAI()
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {str(e)}")

            logger.info(f"Initializing Neo4j connection to {NEO4J_URI}")

            # Initialize LangChain Neo4j Graph
            # Try with schema refresh (requires APOC), fall back to without
            try:
                self.graph = Neo4jGraph(
                    url=NEO4J_URI,
                    username=NEO4J_USERNAME,
                    password=NEO4J_PASSWORD,
                    database=NEO4J_DATABASE,
                )
            except Exception:
                logger.warning(
                    "Neo4j schema refresh failed (APOC?), retrying without schema"
                )
                self.graph = Neo4jGraph(
                    url=NEO4J_URI,
                    username=NEO4J_USERNAME,
                    password=NEO4J_PASSWORD,
                    database=NEO4J_DATABASE,
                    refresh_schema=False,
                )

            # Also initialize a Neo4j driver for direct query execution
            self.driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
            )

            # Test the connection with a simple query
            try:
                schema = self.graph.get_schema
                logger.info("Successfully initialized Neo4j connection")
            except Exception as e:
                logger.error(f"Error connecting to Neo4j: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Error initializing Neo4j connection: {str(e)}")
            self.graph = None
            self.driver = None

    def _resolve_service_name(self, service_name: str) -> str:
        """Resolve a short service name to the full otel-demo deployment name.

        Tries: exact match, otel-demo- prefix, CONTAINS fallback.
        """
        if not self.driver:
            return service_name
        try:
            with self.driver.session() as session:
                # Exact match first
                r = session.run(
                    "MATCH (d:KubernetesDeployment {name: $name}) RETURN d.name AS n",
                    name=service_name,
                ).single()
                if r:
                    return r["n"]

                # Try with otel-demo- prefix
                prefixed = f"otel-demo-{service_name}"
                r = session.run(
                    "MATCH (d:KubernetesDeployment {name: $name}) RETURN d.name AS n",
                    name=prefixed,
                ).single()
                if r:
                    return r["n"]

                # CONTAINS fallback
                r = session.run(
                    "MATCH (d:KubernetesDeployment) WHERE d.name CONTAINS $name RETURN d.name AS n LIMIT 1",
                    name=service_name,
                ).single()
                if r:
                    return r["n"]

                # Also try KubernetesService
                r = session.run(
                    "MATCH (s:KubernetesService) WHERE s.name CONTAINS $name RETURN s.name AS n LIMIT 1",
                    name=service_name,
                ).single()
                if r:
                    return r["n"]
        except Exception as e:
            logger.warning(f"Error resolving service name '{service_name}': {e}")
        return service_name

    def get_service_information(self, service_name: str) -> Dict[str, Any]:
        """Get information about a specific service including deployment, dependencies, and blast radius."""
        logger.info(f"Retrieving information for service: {service_name}")
        resolved = self._resolve_service_name(service_name)
        logger.info(f"Resolved service name: {service_name} -> {resolved}")

        try:
            with self.driver.session() as session:
                # Get deployment info
                deploy_query = """
                MATCH (ns:KubernetesNamespace)-[:HAS_DEPLOYMENT]->(d:KubernetesDeployment)
                WHERE d.name = $name
                OPTIONAL MATCH (ns)-[:HAS_SERVICE]->(s:KubernetesService)-[:ROUTES_TO]->(d)
                RETURN ns.name AS namespace, d.name AS deployment, d.replicas AS replicas,
                       d.image AS image, d.language AS language, d.port AS port,
                       s.name AS service, s.type AS service_type, s.port AS service_port
                """
                deploy_result = session.run(deploy_query, name=resolved).data()

                # Get upstream dependencies (who calls this service)
                upstream_query = """
                MATCH (upstream:KubernetesDeployment)-[r:DEPENDS_ON]->(d:KubernetesDeployment {name: $name})
                RETURN upstream.name AS service, r.via AS via
                """
                upstream = session.run(upstream_query, name=resolved).data()

                # Get downstream dependencies (what this service calls)
                downstream_query = """
                MATCH (d:KubernetesDeployment {name: $name})-[r:DEPENDS_ON]->(downstream)
                RETURN downstream.name AS service, r.via AS via, labels(downstream)[0] AS type
                """
                downstream = session.run(downstream_query, name=resolved).data()

                # Get configmaps used
                cm_query = """
                MATCH (d:KubernetesDeployment {name: $name})-[:USES_CONFIGMAP]->(cm:KubernetesConfigMap)
                RETURN cm.name AS configmap, cm.description AS description
                """
                configmaps = session.run(cm_query, name=resolved).data()

                result = {
                    "resolved_name": resolved,
                    "deployment": deploy_result[0] if deploy_result else {},
                    "upstream_dependents": upstream,
                    "downstream_dependencies": downstream,
                    "configmaps": configmaps,
                    "blast_radius": {
                        "upstream_count": len(upstream),
                        "downstream_count": len(downstream),
                        "affected_services": [u["service"] for u in upstream],
                    },
                }

                logger.info(
                    f"Service info for {resolved}: {len(upstream)} upstream, "
                    f"{len(downstream)} downstream deps"
                )
                return result

        except Exception as e:
            logger.error(f"Error querying service information: {str(e)}")
            return {"error": str(e), "resolved_name": resolved}

    def get_alert_context(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve context information for an alert from the knowledge graph."""
        logger.info("Retrieving context for alert")

        service_name = self._extract_service_from_alert(alert_data)
        if not service_name:
            logger.warning("Could not extract service name from alert")
            return {}

        logger.info(f"Extracted service name from alert: {service_name}")

        result = {"service_name": service_name}

        # Get service information (includes dependencies and blast radius)
        service_info = self.get_service_information(service_name)
        if service_info:
            result["service_info"] = service_info

        # Get connected components for dependency graph
        try:
            related = self.get_component_relationships(service_name)
            if related.get("relationships"):
                result["connected_components"] = related
        except Exception as e:
            logger.error(f"Error getting component relationships: {str(e)}")

        # Get cluster status summary
        try:
            k8s_status = self.get_kubernetes_status(service_name)
            result["kubernetes_status"] = k8s_status
        except Exception as e:
            logger.error(f"Error getting Kubernetes status: {str(e)}")

        return result

    def get_component_relationships(
        self, component_name: str, depth: int = 1
    ) -> Dict[str, Any]:
        """Find relationships for a specific component."""
        logger.info(
            f"Finding relationships for component: {component_name} with depth {depth}"
        )
        resolved = self._resolve_service_name(component_name)

        try:
            with self.driver.session() as session:
                # Get all direct relationships (both directions)
                query = """
                MATCH (source)-[r]->(target)
                WHERE source.name = $name OR target.name = $name
                RETURN source.name AS source, target.name AS target,
                       type(r) AS relationship_type, properties(r) AS props
                """
                result = session.run(query, name=resolved).data()

            relationships = []
            for record in result:
                relationships.append(
                    {
                        "from": record.get("source", "?"),
                        "to": record.get("target", "?"),
                        "type": record.get("relationship_type", "UNKNOWN"),
                        "properties": record.get("props", {}),
                    }
                )

            return {
                "component_name": resolved,
                "relationships": relationships,
                "depth": depth,
            }

        except Exception as e:
            logger.error(f"Error getting component relationships: {str(e)}")
            return {"error": str(e), "component_name": resolved}

    def get_kubernetes_status(self, component_name: str = None) -> Dict[str, Any]:
        """Get the current status of Kubernetes resources from the graph."""
        logger.info(
            f"Retrieving Kubernetes status for component: {component_name or 'all'}"
        )

        try:
            if component_name:
                resolved = self._resolve_service_name(component_name)
                # Get deployment details for specific component
                query = """
                MATCH (ns:KubernetesNamespace)-[:HAS_DEPLOYMENT]->(d:KubernetesDeployment)
                WHERE d.name = $name
                OPTIONAL MATCH (ns)-[:HAS_SERVICE]->(s:KubernetesService)-[:ROUTES_TO]->(d)
                RETURN ns.name AS namespace, d.name AS deployment,
                       d.replicas AS replicas, d.image AS image, d.language AS language,
                       s.name AS service, s.port AS port
                """
                result = self.graph.query(query, {"name": resolved})
                return {"deployments": result, "resolved_name": resolved}
            else:
                # Get overall cluster status summary
                status_query = """
                MATCH (c:KubernetesCluster)-[:HAS_NAMESPACE]->(ns:KubernetesNamespace)
                OPTIONAL MATCH (ns)-[:HAS_DEPLOYMENT]->(d:KubernetesDeployment)
                RETURN c.name AS cluster, ns.name AS namespace,
                       count(d) AS deployment_count
                """
                return self.graph.query(status_query)

        except Exception as e:
            logger.error(f"Error querying Kubernetes status: {str(e)}")
            return {"error": str(e)}

    def generate_cypher_from_question(
        self, question: str, model: str = "gpt-3.5-turbo"
    ) -> Dict[str, Any]:
        """Generate a Cypher query from a natural language question and execute it"""
        logger.info(f"Generating Cypher for question: {question}")

        # Check if we have an LLM-based implementation to generate Cypher
        if self.openai_client:
            # Use OpenAI to generate Cypher
            try:
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that generates Cypher queries for Neo4j from natural language questions. The Neo4j database contains information about Kubernetes resources. Focus on creating accurate, efficient queries. The schema includes nodes like KubernetesCluster, KubernetesNamespace, KubernetesPod, KubernetesContainer, KubernetesService, KubernetesSecret with relationships such as HAS_NAMESPACE, HAS_POD, HAS_SERVICE, HAS_SECRET, HAS_CONTAINER, SERVES_POD.",
                        },
                        {
                            "role": "user",
                            "content": f"Generate a Cypher query to answer this question about Kubernetes resources: '{question}'. Return ONLY the Cypher query, no explanations.",
                        },
                    ],
                    temperature=0.1,
                )

                cypher = response.choices[0].message.content.strip()

                # Add additional pod search patterns if we're looking for service information
                if "payments-service" in question.lower() and "pod" in question.lower():
                    # Also try to match pods with the service name in their name
                    additional_query = """
                    // Also try to find pods that contain the service name in their name
                    MATCH (p:KubernetesPod)
                    WHERE p.name CONTAINS 'payments-service'
                    RETURN p;
                    """
                    cypher = cypher + "\n\n" + additional_query

                # Check for relationship-focused questions
                if (
                    "relationship" in question.lower()
                    and "payments-service" in question.lower()
                ):
                    # Add alternative relationship patterns
                    additional_relationship_query = """
                    // Check for pods related to the service by name pattern
                    MATCH (ns:KubernetesNamespace)-[:HAS_POD]->(pod:KubernetesPod)
                    WHERE pod.name CONTAINS 'payments-service'
                    RETURN ns, pod, 'HAS_POD' as relationship;
                    """
                    cypher = cypher + "\n\n" + additional_relationship_query

                # Execute the generated Cypher query
                logger.info(f"Executing generated Cypher: {cypher}")

                result = None
                try:
                    with self.driver.session() as session:
                        result = session.run(cypher).data()
                except Exception as e:
                    return {"question": question, "cypher": cypher, "error": str(e)}

                return {"question": question, "cypher": cypher, "result": result}

            except Exception as e:
                logger.error(f"Error generating Cypher: {str(e)}")
                return {"question": question, "cypher": "", "error": str(e)}
        else:
            # Simple rule-based fallback implementation
            if "status" in question.lower() and "service" in question.lower():
                # Extract service name
                service_name = "unknown-service"
                if "payments-service" in question.lower():
                    service_name = "payments-service"

                cypher = f"""MATCH (service:KubernetesService {{name: "{service_name}"}})-[:SERVES_POD]->(pod:KubernetesPod)
RETURN pod.status_phase"""

                # Add additional pod search pattern
                additional_query = f"""
                // Also try to find pods that contain the service name in their name
                MATCH (p:KubernetesPod)
                WHERE p.name CONTAINS '{service_name}'
                RETURN p.name, p.status_phase;
                """
                cypher = cypher + "\n\n" + additional_query

            elif "pod" in question.lower() and "service" in question.lower():
                # Extract service name
                service_name = "unknown-service"
                if "payments-service" in question.lower():
                    service_name = "payments-service"

                cypher = f"""MATCH (s:KubernetesService {{name: "{service_name}"}})-[:SERVES_POD]->(p:KubernetesPod)
RETURN p;"""

                # Add additional pod search pattern
                additional_query = f"""
                // Also try to find pods that contain the service name in their name
                MATCH (p:KubernetesPod)
                WHERE p.name CONTAINS '{service_name}'
                RETURN p;
                """
                cypher = cypher + "\n\n" + additional_query

            elif "relationship" in question.lower() and "service" in question.lower():
                # Extract service name
                service_name = "unknown-service"
                if "payments-service" in question.lower():
                    service_name = "payments-service"

                cypher = f"""MATCH (n:KubernetesNamespace)-[r:HAS_SERVICE]->(s:KubernetesService {{name: "{service_name}"}})
MATCH (n)-[:HAS_POD]->(p:KubernetesPod)
MATCH (p)-[:HAS_CONTAINER]->(c:KubernetesContainer)
RETURN r, p, c;"""

                # Add additional relationship pattern
                additional_query = f"""
                // Also check for pods related to the service by name pattern
                MATCH (ns:KubernetesNamespace)-[:HAS_POD]->(pod:KubernetesPod)
                WHERE pod.name CONTAINS '{service_name}'
                RETURN ns, pod, 'HAS_POD' as relationship;
                """
                cypher = cypher + "\n\n" + additional_query

            else:
                cypher = "MATCH (n) RETURN n LIMIT 10"

            # Execute the generated Cypher query
            logger.info(f"Executing generated Cypher: {cypher}")

            result = None
            try:
                with self.driver.session() as session:
                    result = session.run(cypher).data()
            except Exception as e:
                return {"question": question, "cypher": cypher, "error": str(e)}

            return {"question": question, "cypher": cypher, "result": result}

    def get_schema(self) -> str:
        """
        Get the schema of the Neo4j graph database.

        Returns:
            String representation of the Neo4j schema
        """
        try:
            return self.graph.get_schema
        except Exception as e:
            logger.error(f"Error retrieving Neo4j schema: {str(e)}")
            return f"Error: {str(e)}"

    def _extract_service_from_alert(self, alert_data: Dict[str, Any]) -> Optional[str]:
        """Extract service name from alert data."""
        logger.info("Attempting to extract service name from alert data")

        # Direct "service" field (most common)
        if "service" in alert_data and alert_data["service"]:
            logger.info(
                f"Found service directly in alert data: {alert_data['service']}"
            )
            return alert_data["service"]

        # Labels
        if "labels" in alert_data and isinstance(alert_data["labels"], dict):
            if "service" in alert_data["labels"]:
                return alert_data["labels"]["service"]

        # Try to extract from alert name and description
        text = " ".join(
            [
                alert_data.get("name", ""),
                alert_data.get("description", ""),
            ]
        ).lower()

        if not text.strip():
            logger.warning("Could not extract service name from alert")
            return None

        # Known otel-demo service keywords (order: specific first)
        service_keywords = [
            "cartservice",
            "checkoutservice",
            "currencyservice",
            "emailservice",
            "paymentservice",
            "productcatalogservice",
            "recommendationservice",
            "shippingservice",
            "adservice",
            "quoteservice",
            "frauddetectionservice",
            "accountingservice",
            "frontendproxy",
            "frontend",
            "loadgenerator",
            "imageprovider",
            "flagd",
            "kafka",
            "valkey",
            "otelcol",
            "jaeger",
            "prometheus",
            "grafana",
            "opensearch",
        ]
        for kw in service_keywords:
            if kw in text.replace("-", "").replace("_", "").replace(" ", ""):
                logger.info(f"Found service keyword '{kw}' in alert text")
                return kw

        # Hyphenated forms (e.g., "cart-service", "cart service")
        service_parts = [
            ("cart", "cartservice"),
            ("checkout", "checkoutservice"),
            ("currency", "currencyservice"),
            ("email", "emailservice"),
            ("payment", "paymentservice"),
            ("product", "productcatalogservice"),
            ("recommendation", "recommendationservice"),
            ("shipping", "shippingservice"),
            ("ad", "adservice"),
            ("quote", "quoteservice"),
            ("fraud", "frauddetectionservice"),
        ]
        for keyword, svc in service_parts:
            if keyword in text:
                logger.info(f"Found keyword '{keyword}' -> {svc}")
                return svc

        logger.warning("Could not extract service name from alert")
        return None

    def get_recent_deployments(self, service_name: str) -> Dict[str, Any]:
        """Retrieve deployment information for a service from the knowledge graph."""
        logger.info(f"Retrieving deployment info for service: {service_name}")
        resolved = self._resolve_service_name(service_name)

        try:
            with self.driver.session() as session:
                query = """
                MATCH (ns:KubernetesNamespace)-[:HAS_DEPLOYMENT]->(d:KubernetesDeployment)
                WHERE d.name = $name
                RETURN d.name AS deployment_name, ns.name AS namespace,
                       d.replicas AS replicas, d.image AS image, d.language AS language
                """
                result = session.run(query, name=resolved).data()

                if result:
                    return {"service_name": resolved, "deployments": result}
                else:
                    logger.warning(f"No deployment found for: {resolved}")
                    return {"service_name": resolved, "deployments": []}
        except Exception as e:
            logger.error(f"Error retrieving deployment info: {str(e)}")
            return {"error": str(e), "service_name": resolved}
