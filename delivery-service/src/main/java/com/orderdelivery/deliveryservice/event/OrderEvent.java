package com.orderdelivery.deliveryservice.event;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Wire format for every Kafka event this project produces/consumes (see
 * order-service's copy of this same record for the full rationale — kept
 * identical in shape across services on purpose, duplicated rather than
 * shared as a library).
 */
public record OrderEvent(
        @JsonProperty("event_id") String eventId,
        @JsonProperty("event_type") String eventType,
        @JsonProperty("order_id") Long orderId,
        @JsonProperty("event_timestamp") LocalDateTime eventTimestamp,
        @JsonProperty("source_service") String sourceService,
        @JsonProperty("payload") Map<String, Object> payload
) {
}
