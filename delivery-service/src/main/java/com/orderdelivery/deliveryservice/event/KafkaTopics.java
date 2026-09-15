package com.orderdelivery.deliveryservice.event;

/** Topic and event-type name constants. See root README's Kafka documentation. */
public final class KafkaTopics {

    public static final String TOPIC_RIDER_ASSIGNED = "rider-assigned";
    public static final String TOPIC_DELIVERY_STARTED = "delivery-started";
    public static final String TOPIC_DELIVERY_COMPLETED = "delivery-completed";
    public static final String TOPIC_DELIVERY_FAILED = "delivery-failed";

    public static final String EVENT_RIDER_ASSIGNED = "RIDER_ASSIGNED";
    public static final String EVENT_DELIVERY_STARTED = "DELIVERY_STARTED";
    public static final String EVENT_DELIVERY_COMPLETED = "DELIVERY_COMPLETED";
    public static final String EVENT_DELIVERY_FAILED = "DELIVERY_FAILED";

    public static final String SOURCE_SERVICE = "delivery-service";

    private KafkaTopics() {
    }
}
