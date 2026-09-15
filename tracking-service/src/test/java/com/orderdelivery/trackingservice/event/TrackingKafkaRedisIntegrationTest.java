package com.orderdelivery.trackingservice.event;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.orderdelivery.trackingservice.dto.AddTrackingEventRequest;
import com.orderdelivery.trackingservice.model.OrderStatus;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Runs against the real, already-running oda_kafka, oda_redis, and
 * oda_postgres containers. @Transactional rolls back Postgres inserts.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class TrackingKafkaRedisIntegrationTest {

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private ObjectMapper objectMapper;
    @Autowired
    private StringRedisTemplate redisTemplate;
    @Autowired
    private JdbcTemplate jdbcTemplate;

    private KafkaConsumer<String, String> testConsumer;
    private KafkaProducer<String, String> testProducer;

    @BeforeEach
    void setUp() {
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "test-observer-" + UUID.randomUUID());
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        testConsumer = new KafkaConsumer<>(consumerProps);
        testConsumer.subscribe(List.of(KafkaTopics.TOPIC_STATUS_CHANGED));
        testConsumer.poll(Duration.ofMillis(500));

        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        testProducer = new KafkaProducer<>(producerProps);
    }

    @AfterEach
    void tearDown() {
        testConsumer.close();
        testProducer.close();
    }

    private Long insertOrder(OrderStatus status) {
        Long customerId = jdbcTemplate.queryForObject("SELECT customer_id FROM customers LIMIT 1", Long.class);
        Long locationId = jdbcTemplate.queryForObject("SELECT location_id FROM locations LIMIT 1", Long.class);
        return jdbcTemplate.queryForObject(
                "INSERT INTO orders (customer_id, delivery_location_id, status, order_placed_at, total_amount, payment_method) " +
                        "VALUES (?, ?, ?, now(), 10.00, 'card') RETURNING order_id",
                Long.class, customerId, locationId, status.name());
    }

    @Test
    void addTrackingEvent_publishesStatusChangedEvent_andWritesThroughCache() throws Exception {
        Long orderId = insertOrder(OrderStatus.PLACED);

        AddTrackingEventRequest request = new AddTrackingEventRequest();
        request.setStatus(OrderStatus.CONFIRMED);
        mockMvc.perform(post("/api/orders/{orderId}/tracking", orderId)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated());

        long deadline = System.currentTimeMillis() + 15_000;
        ConsumerRecord<String, String> found = null;
        while (System.currentTimeMillis() < deadline && found == null) {
            ConsumerRecords<String, String> records = testConsumer.poll(Duration.ofMillis(500));
            for (ConsumerRecord<String, String> record : records) {
                if (String.valueOf(orderId).equals(record.key())) {
                    found = record;
                }
            }
        }
        assertThat(found).as("STATUS_CHANGED event for order %s", orderId).isNotNull();
        JsonNode event = objectMapper.readTree(found.value());
        assertThat(event.get("event_type").asText()).isEqualTo("STATUS_CHANGED");
        assertThat(event.get("payload").get("new_status").asText()).isEqualTo("CONFIRMED");

        assertThat(redisTemplate.opsForValue().get("order:status:" + orderId)).isEqualTo("CONFIRMED");
    }

    @Test
    void getTracking_cacheMiss_fallsBackToPostgresAndRepopulatesCache() throws Exception {
        Long orderId = insertOrder(OrderStatus.PREPARING);
        redisTemplate.delete("order:status:" + orderId);

        mockMvc.perform(get("/api/orders/{orderId}/tracking", orderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.currentStatus").value("PREPARING"));

        assertThat(redisTemplate.opsForValue().get("order:status:" + orderId)).isEqualTo("PREPARING");
    }

    @Test
    void consumingRiderAssignedEvent_updatesCache_andIsIdempotentOnDuplicateDelivery() throws Exception {
        Long orderId = insertOrder(OrderStatus.READY_FOR_PICKUP);
        String eventId = UUID.randomUUID().toString();
        String json = objectMapper.writeValueAsString(Map.of(
                "event_id", eventId,
                "event_type", "RIDER_ASSIGNED",
                "order_id", orderId,
                "event_timestamp", LocalDateTime.now().toString(),
                "source_service", "delivery-service",
                "payload", Map.of("rider_id", 1)
        ));

        // send the SAME event twice (simulating an at-least-once redelivery)
        testProducer.send(new ProducerRecord<>(KafkaTopics.TOPIC_RIDER_ASSIGNED, String.valueOf(orderId), json)).get();
        testProducer.send(new ProducerRecord<>(KafkaTopics.TOPIC_RIDER_ASSIGNED, String.valueOf(orderId), json)).get();

        // wait for the consumer to process and update the cache
        long deadline = System.currentTimeMillis() + 15_000;
        String cached = null;
        while (System.currentTimeMillis() < deadline) {
            cached = redisTemplate.opsForValue().get("order:status:" + orderId);
            if ("RIDER_ASSIGNED".equals(cached)) {
                break;
            }
            Thread.sleep(500);
        }
        assertThat(cached).isEqualTo("RIDER_ASSIGNED");

        // give the (already-processed) duplicate a moment to arrive too, then confirm
        // only ONE row exists in processed_events for this event_id (idempotency)
        Thread.sleep(2000);
        Integer count = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM processed_events WHERE event_id = ?", Integer.class, eventId);
        assertThat(count).isEqualTo(1);
    }
}
