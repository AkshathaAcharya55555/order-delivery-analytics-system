package com.orderdelivery.trackingservice.event;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

import static com.orderdelivery.trackingservice.event.KafkaTopics.*;

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

    public void publishStatusChanged(Long orderId, Map<String, Object> payload) {
        OrderEvent event = new OrderEvent(
                UUID.randomUUID().toString(), EVENT_STATUS_CHANGED, orderId, LocalDateTime.now(), SOURCE_SERVICE, payload);
        try {
            String json = objectMapper.writeValueAsString(event);
            kafkaTemplate.send(TOPIC_STATUS_CHANGED, String.valueOf(orderId), json);
        } catch (Exception e) {
            log.warn("Failed to publish STATUS_CHANGED event for order {}: {}", orderId, e.getMessage());
        }
    }
}
