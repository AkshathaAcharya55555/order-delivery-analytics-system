package com.orderdelivery.deliveryservice.event;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

import static com.orderdelivery.deliveryservice.event.KafkaTopics.*;

/** See order-service's EventPublisher for the full design rationale (identical pattern). */
@Component
public class EventPublisher {

    private static final Logger log = LoggerFactory.getLogger(EventPublisher.class);

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    public EventPublisher(KafkaTemplate<String, String> kafkaTemplate, ObjectMapper objectMapper) {
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
    }

    public void publishRiderAssigned(Long orderId, Map<String, Object> payload) {
        publish(TOPIC_RIDER_ASSIGNED, EVENT_RIDER_ASSIGNED, orderId, payload);
    }

    public void publishDeliveryStarted(Long orderId, Map<String, Object> payload) {
        publish(TOPIC_DELIVERY_STARTED, EVENT_DELIVERY_STARTED, orderId, payload);
    }

    public void publishDeliveryCompleted(Long orderId, Map<String, Object> payload) {
        publish(TOPIC_DELIVERY_COMPLETED, EVENT_DELIVERY_COMPLETED, orderId, payload);
    }

    public void publishDeliveryFailed(Long orderId, Map<String, Object> payload) {
        publish(TOPIC_DELIVERY_FAILED, EVENT_DELIVERY_FAILED, orderId, payload);
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
