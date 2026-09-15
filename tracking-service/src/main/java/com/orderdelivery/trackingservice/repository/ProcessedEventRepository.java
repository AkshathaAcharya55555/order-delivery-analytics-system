package com.orderdelivery.trackingservice.repository;

import com.orderdelivery.trackingservice.entity.ProcessedEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

public interface ProcessedEventRepository extends JpaRepository<ProcessedEvent, String> {

    /**
     * Atomically records that an event has been processed. Returns 1 if this
     * event_id was new (caller should proceed with the side effect), or 0 if
     * it already existed (a duplicate delivery — caller must skip the side
     * effect entirely). Using ON CONFLICT rather than existsById()+save()
     * closes the race window between check and insert.
     */
    @Modifying
    @Transactional
    @Query(value = "INSERT INTO processed_events (event_id, event_type, order_id, consumer_group, processed_at) " +
            "VALUES (:eventId, :eventType, :orderId, :consumerGroup, now()) " +
            "ON CONFLICT (event_id) DO NOTHING", nativeQuery = true)
    int tryMarkProcessed(@Param("eventId") String eventId, @Param("eventType") String eventType,
                          @Param("orderId") Long orderId, @Param("consumerGroup") String consumerGroup);
}
