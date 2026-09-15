package com.orderdelivery.orderservice.event;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.orderdelivery.orderservice.dto.CreateOrderRequest;
import com.orderdelivery.orderservice.dto.OrderItemRequest;
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
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

/**
 * Runs against the real, already-running oda_kafka and oda_redis containers
 * (see root docker-compose.yml). Uses a raw KafkaConsumer (not @KafkaListener)
 * so this test observes exactly what's on the wire, independent of this
 * service's own producer code being "correct" by its own definition.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
class KafkaRedisIntegrationTest {

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private ObjectMapper objectMapper;
    @Autowired
    private StringRedisTemplate redisTemplate;

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
        testConsumer.subscribe(List.of(KafkaTopics.TOPIC_ORDER_CREATED, KafkaTopics.TOPIC_ORDER_CANCELLED));
        testConsumer.poll(Duration.ofMillis(500)); // trigger partition assignment before the real test starts producing
    }

    @AfterEach
    void tearDownConsumer() {
        testConsumer.close();
    }

    private CreateOrderRequest validRequest() {
        CreateOrderRequest request = new CreateOrderRequest();
        request.setCustomerId(1L);
        request.setDeliveryLocationId(1L);
        request.setPaymentMethod("card");
        OrderItemRequest item = new OrderItemRequest();
        item.setProductName("Kafka Test Item");
        item.setCategory("main");
        item.setUnitPrice(new BigDecimal("5.00"));
        item.setQuantity(1);
        request.setItems(List.of(item));
        return request;
    }

    @Test
    void createOrder_publishesOrderCreatedEvent_withCorrectSchema() throws Exception {
        String response = mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andReturn().getResponse().getContentAsString();
        Long orderId = objectMapper.readTree(response).get("orderId").asLong();

        ConsumerRecord<String, String> record = pollForOrderEvent(orderId, KafkaTopics.TOPIC_ORDER_CREATED);

        assertThat(record).as("ORDER_CREATED event for order %s", orderId).isNotNull();
        JsonNode event = objectMapper.readTree(record.value());
        assertThat(event.get("event_id").asText()).isNotBlank();
        assertThat(event.get("event_type").asText()).isEqualTo("ORDER_CREATED");
        assertThat(event.get("order_id").asLong()).isEqualTo(orderId);
        assertThat(event.get("source_service").asText()).isEqualTo("order-service");
        assertThat(event.get("event_timestamp").asText()).isNotBlank();
        assertThat(event.get("payload")).isNotNull();
        assertThat(record.key()).isEqualTo(String.valueOf(orderId)); // partition key = order_id
    }

    @Test
    void createOrder_writesThroughToRedisStatusCache() throws Exception {
        String response = mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andReturn().getResponse().getContentAsString();
        Long orderId = objectMapper.readTree(response).get("orderId").asLong();

        String cached = redisTemplate.opsForValue().get("order:status:" + orderId);
        assertThat(cached).isEqualTo("PLACED");

        Long ttl = redisTemplate.getExpire("order:status:" + orderId);
        assertThat(ttl).isGreaterThan(0);
    }

    @Test
    void cancelOrder_publishesOrderCancelledEvent_andUpdatesCache() throws Exception {
        String createResponse = mockMvc.perform(post("/api/orders")
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andReturn().getResponse().getContentAsString();
        Long orderId = objectMapper.readTree(createResponse).get("orderId").asLong();

        mockMvc.perform(put("/api/orders/{id}/cancel", orderId));

        ConsumerRecord<String, String> record = pollForOrderEvent(orderId, KafkaTopics.TOPIC_ORDER_CANCELLED);
        assertThat(record).as("ORDER_CANCELLED event for order %s", orderId).isNotNull();
        JsonNode event = objectMapper.readTree(record.value());
        assertThat(event.get("event_type").asText()).isEqualTo("ORDER_CANCELLED");
        assertThat(event.get("payload").get("previous_status").asText()).isEqualTo("PLACED");

        assertThat(redisTemplate.opsForValue().get("order:status:" + orderId)).isEqualTo("CANCELLED");
    }

    private ConsumerRecord<String, String> pollForOrderEvent(Long orderId, String topic) {
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
}
