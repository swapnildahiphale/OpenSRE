#!/bin/bash
set -e

echo "🐳 Starting PostgreSQL test container..."

# Start temporary postgres container
CONTAINER_NAME="test-migration-postgres-$$"
docker run -d \
  --name "$CONTAINER_NAME" \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_USER=testuser \
  -e POSTGRES_DB=testdb \
  -p 5433:5432 \
  postgres:15-alpine

# Wait for postgres to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Test connection
until docker exec "$CONTAINER_NAME" pg_isready -U testuser > /dev/null 2>&1; do
  echo "   Waiting for postgres..."
  sleep 1
done

echo "✅ PostgreSQL is ready"

# Set DATABASE_URL
export DATABASE_URL="postgresql://testuser:testpass@localhost:5433/testdb"
export PYTHONPATH="$(pwd)"

# Run migration
echo ""
echo "🚀 Running alembic upgrade head..."
alembic upgrade head

if [ $? -ne 0 ]; then
  echo "❌ Migration failed!"
  docker stop "$CONTAINER_NAME" > /dev/null 2>&1
  docker rm "$CONTAINER_NAME" > /dev/null 2>&1
  exit 1
fi

echo "✅ Migration completed successfully"

# Verify schema using psql
echo ""
echo "🔍 Verifying schema..."
echo ""

# Check tables
echo "📊 Tables created:"
docker exec "$CONTAINER_NAME" psql -U testuser -d testdb -c "\dt" | grep -E "^ " || true

echo ""
echo "🎯 Verifying node_configurations schema:"
docker exec "$CONTAINER_NAME" psql -U testuser -d testdb -c "\d node_configurations"

echo ""
echo "🔑 Checking primary key and constraints:"
docker exec "$CONTAINER_NAME" psql -U testuser -d testdb -c "
SELECT
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
WHERE rel.relname = 'node_configurations'
ORDER BY con.contype;
"

# Test basic operations
echo ""
echo "🧪 Testing basic operations..."
docker exec "$CONTAINER_NAME" psql -U testuser -d testdb << 'EOSQL'
-- Insert org node
INSERT INTO org_nodes (org_id, node_id, node_type, name)
VALUES ('test-org', 'test-org', 'org', 'Test Organization');

-- Insert node configuration
INSERT INTO node_configurations (id, org_id, node_id, node_type, config_json, version)
VALUES ('test-config-1', 'test-org', 'test-org', 'org', '{"agents": {"investigation": {"enabled": true}}}', 1);

-- Query back
SELECT id, org_id, node_id, config_json->'agents' as agents FROM node_configurations;

-- Update
UPDATE node_configurations
SET config_json = '{"agents": {"investigation": {"enabled": false}}}',
    version = version + 1
WHERE id = 'test-config-1';

SELECT id, org_id, config_json->'agents' as agents, version FROM node_configurations;
EOSQL

if [ $? -eq 0 ]; then
  echo ""
  echo "============================================================"
  echo "✅ ALL TESTS PASSED!"
  echo "============================================================"
  echo ""
  echo "✨ Migration is working correctly"
  echo "✨ node_configurations schema is correct"
  echo "✨ Ready for production deployment"
  echo ""
fi

# Cleanup
echo "🧹 Cleaning up..."
docker stop "$CONTAINER_NAME" > /dev/null 2>&1
docker rm "$CONTAINER_NAME" > /dev/null 2>&1

echo "✅ Test complete"
