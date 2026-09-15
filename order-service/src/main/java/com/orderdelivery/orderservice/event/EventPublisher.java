package com.orderdelivery.orderservice.event;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

import static com.orderdelivery.orderservice.event.KafkaTopics.*;

/**
 * Publishes domain events to Kafka. Fire-and-forget from the caller's point
 * of view: a publish failure is logged but never fails the HTTP request that
 * triggered it (the order/cancel already committed to Postgres by the time
 * this runs — Kafka is an additive side channel here, not a dependency the
 * core write path relies on). See README's "ordering considerations" for
 * why order_id is used as the partition key.
 */
@Component
public class EventPublisher {

    private static final Logger log = LoggerFactory.getLogger(EventPublisher.class);

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    public EventPublisher(KafkaTemplate<String, String> kafkaTemplate, ObjectMapper objectMapper) {
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
    }

    public void publishOrderCreated(Long orderId, Map<String, Object> payload) {
        publish(TOPIC_ORDER_CREATED, EVENT_ORDER_CREATED, orderId, payload);
    }

    public void publishOrderCancelled(Long orderId, Map<String, Object> payload) {
        publish(TOPIC_ORDER_CANCELLED, EVENT_ORDER_CANCELLED, orderId, payload);
    }

    private void publish(String topic, String eventType, Long orderId, Map<String, Object> payload) {
        OrderEvent event = new OrderEvent(
                UUID.randomUUID().toString(), eventType, orderId, LocalDateTime.now(), SOURCE_SERVICE, payload);
        try {
            String json = objectMapper.writeValueAsString(event);
            kafkaTemplate.send(topic, String.valueOf(orderId), json);
        } catch (Exception e) {
            log.warn("Failed to publish {} event for order {}: {}", eventType, orderId, e.getMessage());
        }
    }
}
