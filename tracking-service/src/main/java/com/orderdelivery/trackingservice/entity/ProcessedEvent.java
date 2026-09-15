package com.orderdelivery.trackingservice.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/**
 * One row per successfully processed Kafka event, keyed by the producer's
 * own event_id — see ProcessedEventRepository.tryMarkProcessed for how this
 * is used as an atomic idempotency guard (INSERT ... ON CONFLICT DO NOTHING).
 */
@Entity
@Table(name = "processed_events")
public class ProcessedEvent {

    @Id
    @Column(name = "event_id")
    private String eventId;

    @Column(name = "event_type", nullable = false)
    private String eventType;

    @Column(name = "order_id")
    private Long orderId;

    @Column(name = "consumer_group", nullable = false)
    private String consumerGroup;

    @Column(name = "processed_at", insertable = false, updatable = false)
    private LocalDateTime processedAt;

    protected ProcessedEvent() {
    }

    public String getEventId() {
        return eventId;
    }
}
