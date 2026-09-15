package com.orderdelivery.orderservice.event;

/**
 * Topic and event-type name constants. One topic per event type (7 total
 * across the whole system) — see root README's Kafka documentation for the
 * full topic/producer/consumer map.
 */
public final class KafkaTopics {

    public static final String TOPIC_ORDER_CREATED = "order-created";
    public static final String TOPIC_ORDER_CANCELLED = "order-cancelled";

    public static final String EVENT_ORDER_CREATED = "ORDER_CREATED";
    public static final String EVENT_ORDER_CANCELLED = "ORDER_CANCELLED";

    public static final String SOURCE_SERVICE = "order-service";

    private KafkaTopics() {
    }
}
