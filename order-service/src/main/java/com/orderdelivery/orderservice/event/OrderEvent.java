package com.orderdelivery.orderservice.event;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Wire format for every Kafka event this project produces/consumes, shared
 * across services by identical shape (JSON), not by a shared Java library —
 * each service keeps its own copy of this record, deliberately.
 * Field names are wire-fixed to snake_case per the project's event contract,
 * independent of Spring MVC's own (camelCase) REST JSON, which is untouched.
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
