package com.orderdelivery.deliveryservice.event;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.orderdelivery.deliveryservice.dto.CreateRiderRequest;
import com.orderdelivery.deliveryservice.dto.UpdateAvailabilityRequest;
import com.orderdelivery.deliveryservice.dto.UpdateDeliveryStatusRequest;
import com.orderdelivery.deliveryservice.model.DeliveryStatus;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
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

import java.math.BigDecimal;
import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Runs against the real, already-running oda_kafka and oda_redis containers.
 * @Transactional rolls back Postgres inserts; Kafka/Redis state from a test
 * is harmless to leave behind (unique per-test order/rider ids).
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class DeliveryKafkaRedisIntegrationTest {

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private ObjectMapper objectMapper;
    @Autowired
    private StringRedisTemplate redisTemplate;
    @Autowired
    private JdbcTemplate jdbcTemplate;

    private KafkaConsumer<String, String> testConsumer;

    @BeforeEach
    void setUpConsumer() {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "test-observer-" + UUID.randomUUID());
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        testConsumer = new KafkaConsumer<>(props);
        testConsumer.subscribe(List.of(
                KafkaTopics.TOPIC_RIDER_ASSIGNED, KafkaTopics.TOPIC_DELIVERY_STARTED,
                KafkaTopics.TOPIC_DELIVERY_COMPLETED, KafkaTopics.TOPIC_DELIVERY_FAILED));
        testConsumer.poll(Duration.ofMillis(500));
    }

    @AfterEach
    void tearDownConsumer() {
        testConsumer.close();
    }

    private Long insertLocation(String city, double lat, double lon) {
        return jdbcTemplate.queryForObject(
                "INSERT INTO locations (address_line, city, state, latitude, longitude) " +
                        "VALUES ('1 Kafka Test St', ?, 'TX', ?, ?) RETURNING location_id",
                Long.class, city, lat, lon);
    }

    private Long insertReadyOrder(Long locationId) {
        Long customerId = jdbcTemplate.queryForObject("SELECT customer_id FROM customers LIMIT 1", Long.class);
        return jdbcTemplate.queryForObject(
                "INSERT INTO orders (customer_id, delivery_location_id, status, order_placed_at, total_amount, payment_method) " +
                        "VALUES (?, ?, 'READY_FOR_PICKUP', now(), 10.00, 'card') RETURNING order_id",
                Long.class, customerId, locationId);
    }

    private CreateRiderRequest riderRequest(String city) {
        CreateRiderRequest request = new CreateRiderRequest();
        request.setFirstName("Kafka");
        request.setLastName("Tester");
        request.setPhone("555-9999");
        request.setVehicleType("bike");
        request.setCity(city);
        request.setRating(new BigDecimal("4.5"));
        return request;
    }

    private ConsumerRecord<String, String> pollFor(String topic, Long orderId) {
        long deadline = System.currentTimeMillis() + 15_000;
        while (System.currentTimeMillis() < deadline) {
            ConsumerRecords<String, String> records = testConsumer.poll(Duration.ofMillis(500));
            for (ConsumerRecord<String, String> record : records) {
                if (record.topic().equals(topic) && String.valueOf(orderId).equals(record.key())) {
                    return record;
                }
            }
        }
        return null;
    }

    @Test
    void assignRider_publishesRiderAssignedEvent() throws Exception {
        Long locationId = insertLocation("Denver", 39.7392, -104.9903);
        Long orderId = insertReadyOrder(locationId);
        mockMvc.perform(post("/api/riders").contentType("application/json")
                .content(objectMapper.writeValueAsString(riderRequest("Denver"))));

        mockMvc.perform(post("/api/deliveries/{orderId}/assign", orderId)).andExpect(status().isCreated());

        ConsumerRecord<String, String> record = pollFor(KafkaTopics.TOPIC_RIDER_ASSIGNED, orderId);
        assertThat(record).as("RIDER_ASSIGNED event for order %s", orderId).isNotNull();
        JsonNode event = objectMapper.readTree(record.value());
        assertThat(event.get("event_type").asText()).isEqualTo("RIDER_ASSIGNED");
        assertThat(event.get("source_service").asText()).isEqualTo("delivery-service");
        assertThat(event.get("payload").get("rider_id")).isNotNull();
    }

    @Test
    void deliveryStatusUpdates_publishStartedThenCompleted() throws Exception {
        Long locationId = insertLocation("Miami", 25.7617, -80.1918);
        Long orderId = insertReadyOrder(locationId);
        mockMvc.perform(post("/api/riders").contentType("application/json")
                .content(objectMapper.writeValueAsString(riderRequest("Miami"))));
        mockMvc.perform(post("/api/deliveries/{orderId}/assign", orderId));

        UpdateDeliveryStatusRequest pickedUp = new UpdateDeliveryStatusRequest();
        pickedUp.setStatus(DeliveryStatus.PICKED_UP);
        mockMvc.perform(put("/api/deliveries/{orderId}/status", orderId).contentType("application/json")
                .content(objectMapper.writeValueAsString(pickedUp)));

        UpdateDeliveryStatusRequest outForDelivery = new UpdateDeliveryStatusRequest();
        outForDelivery.setStatus(DeliveryStatus.OUT_FOR_DELIVERY);
        mockMvc.perform(put("/api/deliveries/{orderId}/status", orderId).contentType("application/json")
                .content(objectMapper.writeValueAsString(outForDelivery)));

        assertThat(pollFor(KafkaTopics.TOPIC_DELIVERY_STARTED, orderId)).as("DELIVERY_STARTED").isNotNull();

        UpdateDeliveryStatusRequest delivered = new UpdateDeliveryStatusRequest();
        delivered.setStatus(DeliveryStatus.DELIVERED);
        mockMvc.perform(put("/api/deliveries/{orderId}/status", orderId).contentType("application/json")
                .content(objectMapper.writeValueAsString(delivered)));

        assertThat(pollFor(KafkaTopics.TOPIC_DELIVERY_COMPLETED, orderId)).as("DELIVERY_COMPLETED").isNotNull();
    }

    @Test
    void updateAvailability_writesThroughToRedis_andGetAvailabilityReadsFromCache() throws Exception {
        String response = mockMvc.perform(post("/api/riders").contentType("application/json")
                        .content(objectMapper.writeValueAsString(riderRequest("Austin"))))
                .andReturn().getResponse().getContentAsString();
        Long riderId = objectMapper.readTree(response).get("riderId").asLong();

        // created riders default to available=true, cached immediately on create
        assertThat(redisTemplate.opsForValue().get("rider:available:" + riderId)).isEqualTo("true");

        UpdateAvailabilityRequest req = new UpdateAvailabilityRequest();
        req.setAvailable(false);
        mockMvc.perform(put("/api/riders/{id}/availability", riderId).contentType("application/json")
                .content(objectMapper.writeValueAsString(req)));

        assertThat(redisTemplate.opsForValue().get("rider:available:" + riderId)).isEqualTo("false");

        Long ttl = redisTemplate.getExpire("rider:available:" + riderId);
        assertThat(ttl).isGreaterThan(0);

        mockMvc.perform(get("/api/riders/{id}/availability", riderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.available").value(false));
    }

    @Test
    void getAvailability_cacheMiss_fallsBackToPostgresAndRepopulatesCache() throws Exception {
        String response = mockMvc.perform(post("/api/riders").contentType("application/json")
                        .content(objectMapper.writeValueAsString(riderRequest("Seattle"))))
                .andReturn().getResponse().getContentAsString();
        Long riderId = objectMapper.readTree(response).get("riderId").asLong();

        redisTemplate.delete("rider:available:" + riderId); // force a cache miss

        mockMvc.perform(get("/api/riders/{id}/availability", riderId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.available").value(true)); // fell back to Postgres correctly

        assertThat(redisTemplate.opsForValue().get("rider:available:" + riderId))
                .as("cache should be repopulated after the miss")
                .isEqualTo("true");
    }
}
