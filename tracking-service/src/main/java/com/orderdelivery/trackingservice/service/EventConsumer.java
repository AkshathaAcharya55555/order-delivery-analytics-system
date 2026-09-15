package com.orderdelivery.trackingservice.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.orderdelivery.trackingservice.cache.OrderStatusCache;
import com.orderdelivery.trackingservice.event.KafkaTopics;
import com.orderdelivery.trackingservice.event.OrderEvent;
import com.orderdelivery.trackingservice.model.OrderStatus;
import com.orderdelivery.trackingservice.repository.ProcessedEventRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

import java.util.Map;

/**
 * Consumes the six upstream event topics (everything except status-changed,
 * which this service itself produces) to keep the shared order-status Redis
 * cache coherent across services, with idempotent processing keyed on
 * event_id (see ProcessedEventRepository.tryMarkProcessed).
 *
 * This consumer deliberately does NOT write to order_status_history or
 * orders.status — those are already written synchronously by order-service
 * and delivery-service in the same transaction as their own DB changes.
 * Re-deriving them here from Kafka too would create two independent writers
 * for the same rows. This consumer's only job is cache coherence.
 *
 * Single consumer group ("tracking-service-group", one listener container
 * per topic below, default concurrency 1) — see root README's "ordering
 * considerations" for why a single partition per topic plus order_id as the
 * producer's partition key is sufficient here without adding
 * multi-partition/multi-consumer complexity this project doesn't need yet.
 */
@Service
public class EventConsumer {

    private static final Logger log = LoggerFactory.getLogger(EventConsumer.class);

    private static final Map<String, OrderStatus> STATUS_BY_EVENT_TYPE = Map.of(
            "ORDER_CREATED", OrderStatus.PLACED,
            "ORDER_CANCELLED", OrderStatus.CANCELLED,
            "RIDER_ASSIGNED", OrderStatus.RIDER_ASSIGNED,
            "DELIVERY_STARTED", OrderStatus.OUT_FOR_DELIVERY,
            "DELIVERY_COMPLETED", OrderStatus.DELIVERED,
            "DELIVERY_FAILED", OrderStatus.FAILED
    );

    private final ProcessedEventRepository processedEventRepository;
    private final OrderStatusCache orderStatusCache;
    private final ObjectMapper objectMapper;

    public EventConsumer(ProcessedEventRepository processedEventRepository, OrderStatusCache orderStatusCache,
                          ObjectMapper objectMapper) {
        this.processedEventRepository = processedEventRepository;
        this.orderStatusCache = orderStatusCache;
        this.objectMapper = objectMapper;
    }

    @KafkaListener(topics = {
            KafkaTopics.TOPIC_ORDER_CREATED, KafkaTopics.TOPIC_ORDER_CANCELLED, KafkaTopics.TOPIC_RIDER_ASSIGNED,
            KafkaTopics.TOPIC_DELIVERY_STARTED, KafkaTopics.TOPIC_DELIVERY_COMPLETED, KafkaTopics.TOPIC_DELIVERY_FAILED
    }, groupId = KafkaTopics.CONSUMER_GROUP)
    public void onEvent(String json) {
        OrderEvent event;
        try {
            event = objectMapper.readValue(json, OrderEvent.class);
        } catch (Exception e) {
            log.warn("Failed to parse event, skipping: {}", e.getMessage());
            return;
        }

        int inserted = processedEventRepository.tryMarkProcessed(
                event.eventId(), event.eventType(), event.orderId(), KafkaTopics.CONSUMER_GROUP);
        if (inserted == 0) {
            log.info("Duplicate event {} ({}) for order {} skipped", event.eventId(), event.eventType(), event.orderId());
            return;
        }

        OrderStatus newStatus = STATUS_BY_EVENT_TYPE.get(event.eventType());
        if (newStatus != null) {
            orderStatusCache.put(event.orderId(), newStatus.name());
        }
    }
}
