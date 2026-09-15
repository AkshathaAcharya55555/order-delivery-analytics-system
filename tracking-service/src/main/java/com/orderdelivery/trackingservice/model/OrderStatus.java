package com.orderdelivery.trackingservice.model;

import java.util.EnumSet;
import java.util.Map;
import java.util.Set;

/**
 * Order lifecycle status. Matches the CHECK constraint values in
 * database/schema.sql (orders.status, order_status_history.status) exactly.
 * Duplicated from order-service/delivery-service since these are
 * independent deployables without a shared library in this project.
 *
 * tracking-service is the authority for this full transition matrix — its
 * POST endpoint is the only place that can drive PLACED -> CONFIRMED ->
 * PREPARING -> READY_FOR_PICKUP, the three stages no other service's
 * endpoints cover (order-service only writes PLACED and CANCELLED;
 * delivery-service only writes RIDER_ASSIGNED through DELIVERED/FAILED).
 */
public enum OrderStatus {
    PLACED,
    CONFIRMED,
    PREPARING,
    READY_FOR_PICKUP,
    RIDER_ASSIGNED,
    PICKED_UP,
    OUT_FOR_DELIVERY,
    DELIVERED,
    CANCELLED,
    FAILED;

    private static final Set<OrderStatus> TERMINAL = EnumSet.of(DELIVERED, CANCELLED, FAILED);

    private static final Map<OrderStatus, Set<OrderStatus>> NEXT = Map.of(
            PLACED, EnumSet.of(CONFIRMED, CANCELLED),
            CONFIRMED, EnumSet.of(PREPARING, CANCELLED),
            PREPARING, EnumSet.of(READY_FOR_PICKUP, CANCELLED),
            READY_FOR_PICKUP, EnumSet.of(RIDER_ASSIGNED, CANCELLED),
            RIDER_ASSIGNED, EnumSet.of(PICKED_UP, CANCELLED, FAILED),
            PICKED_UP, EnumSet.of(OUT_FOR_DELIVERY, FAILED),
            OUT_FOR_DELIVERY, EnumSet.of(DELIVERED, FAILED),
            DELIVERED, EnumSet.noneOf(OrderStatus.class),
            CANCELLED, EnumSet.noneOf(OrderStatus.class),
            FAILED, EnumSet.noneOf(OrderStatus.class)
    );

    public boolean isTerminal() {
        return TERMINAL.contains(this);
    }

    public boolean canTransitionTo(OrderStatus next) {
        return NEXT.getOrDefault(this, Set.of()).contains(next);
    }
}
