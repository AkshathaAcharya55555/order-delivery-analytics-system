package com.orderdelivery.orderservice.model;

import java.util.EnumSet;
import java.util.Map;
import java.util.Set;

/**
 * Order lifecycle status. Matches the CHECK constraint values in
 * database/schema.sql (orders.status, order_status_history.status) exactly.
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

    /** Terminal states an order can never leave. */
    private static final Set<OrderStatus> TERMINAL = EnumSet.of(DELIVERED, CANCELLED, FAILED);

    /**
     * Legal next states from each status. order-service only ever transitions
     * orders to PLACED (on creation) and CANCELLED (on cancel); the full
     * matrix is duplicated here (and in delivery-service / tracking-service)
     * so each service can validate the transitions it is responsible for
     * without a runtime dependency on the others.
     */
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
