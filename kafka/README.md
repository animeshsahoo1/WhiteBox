# Kafka Configuration

Standalone Kafka setup for development and testing purposes. The main docker-compose.yml in the root directory includes Kafka, but this folder provides an isolated Kafka environment.

## 📋 Overview

This directory contains a minimal Kafka setup with Zookeeper for local development and testing of producers/consumers independently from the full system.

## 🚀 Quick Start

### Start Kafka

```bash
cd kafka
docker-compose up -d
```

### Verify Services

```bash
# Check running containers
docker-compose ps

# Expected output:
# kafka       Up      9092/tcp
# zookeeper   Up      2181/tcp
```

### Test Kafka

```bash
# Create a test topic
docker exec kafka kafka-topics \
    --create \
    --topic test-topic \
    --bootstrap-server localhost:9092 \
    --partitions 1 \
    --replication-factor 1

# List topics
docker exec kafka kafka-topics \
    --list \
    --bootstrap-server localhost:9092

# Produce messages
docker exec -it kafka kafka-console-producer \
    --topic test-topic \
    --bootstrap-server localhost:9092

# Consume messages (in another terminal)
docker exec kafka kafka-console-consumer \
    --topic test-topic \
    --bootstrap-server localhost:9092 \
    --from-beginning
```

## 🔧 Configuration

The `docker-compose.yml` in this directory configures:
- **Zookeeper**: Port 2181
- **Kafka Broker**: Port 9092
- **Topics**: Auto-create enabled
- **Retention**: 7 days default

## 📊 Topics Used by System

When running the full system, these topics are created:
- `market-data` - Real-time price data
- `news-data` - News articles
- `sentiment-data` - Social media sentiment
- `fundamental-data` - Company fundamentals

## 🛠️ Management Commands

### List Topics
```bash
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Describe Topic
```bash
docker exec kafka kafka-topics \
    --describe \
    --topic market-data \
    --bootstrap-server localhost:9092
```

### Delete Topic
```bash
docker exec kafka kafka-topics \
    --delete \
    --topic test-topic \
    --bootstrap-server localhost:9092
```

### View Consumer Groups
```bash
docker exec kafka kafka-consumer-groups \
    --list \
    --bootstrap-server localhost:9092
```

### Check Consumer Lag
```bash
docker exec kafka kafka-consumer-groups \
    --describe \
    --group pathway-market-consumer \
    --bootstrap-server localhost:9092
```

## 🧪 Testing

### Test Producer
```bash
# Send JSON message
echo '{"symbol": "TEST", "price": 100.0}' | \
docker exec -i kafka kafka-console-producer \
    --topic market-data \
    --bootstrap-server localhost:9092
```

### Test Consumer
```bash
# Consume from beginning
docker exec kafka kafka-console-consumer \
    --topic market-data \
    --bootstrap-server localhost:9092 \
    --from-beginning
```

## 🔗 Integration

### Connect from Producers (streaming/)
```python
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
```

### Connect from Consumers (pathway/)
```python
rdkafka_settings = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "my-consumer-group",
    "auto.offset.reset": "earliest"
}

table = pw.io.kafka.read(
    rdkafka_settings,
    topic="market-data",
    format="json",
    schema=MySchema
)
```

## 📝 Notes

- This is for **development only**
- Single broker setup (not production-ready)
- No authentication/encryption configured
- Data persists in Docker volumes

For production deployments, consider:
- Multi-broker cluster
- Replication factor > 1
- Authentication (SASL/SSL)
- Monitoring (Prometheus, Grafana)
- Resource limits and tuning

## 🛑 Shutdown

```bash
# Stop services
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```
