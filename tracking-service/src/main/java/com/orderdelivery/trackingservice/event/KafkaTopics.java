package com.orderdelivery.trackingservice.event;

/**
 * Topic and event-type name constants. tracking-service produces
 * STATUS_CHANGED and consumes the other six topics (see root README's Kafka
 * documentation for the full topic/producer/consumer map and consumer-group
 * rationale).
 */
public final class KafkaTopics {

    public static final String TOPIC_ORDER_CREATED = "order-created";
    public static final String TOPIC_ORDER_CANCELLED = "order-cancelled";
    public static final String TOPIC_RIDER_ASSIGNED = "rider-assigned";
    public static final String TOPIC_DELIVERY_STARTED = "delivery-started";
    public static final String TOPIC_DELIVERY_COMPLETED = "delivery-completed";
    public static final String TOPIC_DELIVERY_FAILED = "delivery-failed";
    public static final String TOPIC_STATUS_CHANGED = "status-changed";

    public static final String EVENT_STATUS_CHANGED = "STATUS_CHANGED";

    public static final String SOURCE_SERVICE = "tracking-service";
    public static final String CONSUMER_GROUP = "tracking-service-group";

    private KafkaTopics() {
    }
}
